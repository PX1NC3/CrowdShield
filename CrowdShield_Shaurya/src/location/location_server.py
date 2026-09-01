"""
CrowdShield - Location Server (Part 1 + Part 2)
================================================
Standalone HTTP server on port 8766.

Implements:
  Part 1 - Location Data Infrastructure
    POST /api/location/update  -- accept a location signal
    GET  /api/location/status  -- server health and aggregate stats

  Part 2 - Geographic Aggregation + Heatmap API
    GET  /api/heatmap              -- all active cells (aggregated)
    GET  /api/heatmap/cell/{id}    -- single cell details

Privacy guarantees (enforced in location_aggregator.py):
  - No individual coordinates stored after grid-snapping.
  - Session IDs are one-way hashed before storage.
  - Density = unique active sessions, NOT total requests.
  - No trajectories or personally identifying information.

This server is SEPARATE from the camera server (port 8765).
It does NOT touch YOLO, tracking, zones, risk, or prevention.

Validation rules enforced:
  - latitude must be a number in [-90, 90]
  - longitude must be a number in [-180, 180]
  - timestamp must be parseable ISO-8601 and not more than 5 minutes stale
  - session_id must be a non-empty string, 1-128 chars, no whitespace-only
  - Malformed JSON returns 400
  - Missing required fields return 400 with a clear error message
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import re
import urllib.parse
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Allow importing from src/ (for shared demo generator & utilities)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, ".."))
sys.path.insert(0, _SCRIPT_DIR)
sys.path.insert(0, _SRC_DIR)

# Ensure demo_generator singleton instance is synchronized across all import paths
try:
    import demo_generator as _dg_mod
    sys.modules["src.demo_generator"] = _dg_mod
except ImportError:
    pass

from location_aggregator import (
    ingest_location,
    cleanup_stale_sessions,
    get_heatmap_snapshot,
    get_cell,
    get_status,
    get_aggregated_flows,
    evaluate_location_risk_and_prevention,
    SESSION_STALE_SECONDS,
    GRID_STEP,
)

def get_demo_generator():
    try:
        import demo_generator as dg
        return dg.demo_generator
    except ImportError:
        try:
            from src import demo_generator as dg
            return dg.demo_generator
        except ImportError:
            return None


# =====================================================
# CONFIGURATION
# =====================================================

HOST = "127.0.0.1"
PORT = 8766

# Maximum age of a submitted timestamp before it is rejected.
MAX_TIMESTAMP_AGE_SECONDS = 5 * 60   # 5 minutes

# Cleanup interval for stale sessions.
CLEANUP_INTERVAL_SECONDS = 60        # every 1 minute

# Regex for cell_id path component -- only safe characters
_CELL_ID_RE = re.compile(r"^[0-9\-_\.]+$")


# =====================================================
# VALIDATION
# =====================================================

class ValidationError(Exception):
    """Raised when an incoming request fails validation."""
    pass


def _validate_latitude(value) -> float:
    try:
        lat = float(value)
    except (TypeError, ValueError):
        raise ValidationError("latitude must be a number")
    if not (-90.0 <= lat <= 90.0):
        raise ValidationError(f"latitude {lat} out of range [-90, 90]")
    return lat


def _validate_longitude(value) -> float:
    try:
        lon = float(value)
    except (TypeError, ValueError):
        raise ValidationError("longitude must be a number")
    if not (-180.0 <= lon <= 180.0):
        raise ValidationError(f"longitude {lon} out of range [-180, 180]")
    return lon


def _validate_timestamp(value) -> None:
    """
    Validate that timestamp is parseable and not more than MAX_TIMESTAMP_AGE_SECONDS stale.
    Future timestamps (up to 60 s clock skew) are accepted.
    """
    if value is None:
        raise ValidationError("timestamp is required")
    if not isinstance(value, str):
        raise ValidationError("timestamp must be a string")

    # Try parsing with and without timezone info
    parsed = None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            parsed = datetime.strptime(value, fmt)
            break
        except ValueError:
            continue

    if parsed is None:
        # Try fromisoformat as fallback (Python 3.7+)
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            raise ValidationError(f"timestamp '{value}' is not valid ISO-8601")

    # Normalise to UTC
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)

    now_utc = datetime.now(timezone.utc)
    age = (now_utc - parsed).total_seconds()

    if age > MAX_TIMESTAMP_AGE_SECONDS:
        raise ValidationError(
            f"timestamp is {int(age)} seconds old (max {MAX_TIMESTAMP_AGE_SECONDS})"
        )
    # Allow up to 60 s future clock skew
    if age < -60:
        raise ValidationError("timestamp is too far in the future")


def _validate_session_id(value) -> str:
    if value is None:
        raise ValidationError("session_id is required")
    if not isinstance(value, str):
        raise ValidationError("session_id must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValidationError("session_id must not be empty or whitespace-only")
    if len(stripped) > 128:
        raise ValidationError("session_id must not exceed 128 characters")
    return stripped


# =====================================================
# STALE SESSION CLEANUP BACKGROUND THREAD
# =====================================================

def _cleanup_loop() -> None:
    """Periodically remove stale sessions from memory."""
    while True:
        time.sleep(CLEANUP_INTERVAL_SECONDS)
        removed = cleanup_stale_sessions()
        if removed > 0:
            print(f"[location_server] Cleaned up {removed} stale session(s).")


_cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True)


# =====================================================
# HTTP HANDLER
# =====================================================

class LocationHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler for the CrowdShield Location API.

    Routes:
      POST /api/location/update        -- Part 1: ingest a location signal
      GET  /api/location/status        -- Part 1: server health
      GET  /api/heatmap                -- Part 2: all active cells
      GET  /api/heatmap/cell/{cell_id} -- Part 2: single cell details
    """

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        dg = get_demo_generator()
        raw_path = self.path
        parsed = urllib.parse.urlparse(raw_path) if "?" in raw_path else None
        query_str = raw_path.split("?")[1] if "?" in raw_path else ""
        query = urllib.parse.parse_qs(query_str) if query_str else {}
        path = raw_path.split("?")[0].rstrip("/")

        role = query.get("role", ["manager"])[0].lower()
        forced_demo = query.get("demo", [None])[0]

        is_demo = (
            forced_demo == "1"
            or forced_demo == "true"
            or (dg is not None and dg.heatmap_enabled)
        )

        # --------------------------------------------------
        # GET /api/demo/status (or /location/demo/status)
        # --------------------------------------------------
        if path in ("/api/demo/status", "/demo/status", "/location/demo/status"):
            payload = {
                "camera_demo": dg.camera_enabled if dg else False,
                "heatmap_demo": dg.heatmap_enabled if dg else False,
                "scenario": dg.scenario if dg else "normal",
                "scenarios_available": ["normal", "buildup", "critical", "dispersal"],
            }
            self._respond(200, json.dumps(payload, indent=2).encode("utf-8"))
            return

        # --------------------------------------------------
        # GET /api/heatmap (and /location/heatmap)
        # --------------------------------------------------
        if path in ("/api/heatmap", "/location/heatmap", "/heatmap"):
            if is_demo and dg:
                demo_data = dg.generate_heatmap_data(user_role=role)
                payload = json.dumps(demo_data["heatmap"]).encode("utf-8")
            else:
                eval_res = evaluate_location_risk_and_prevention(user_role=role)
                raw_cells = get_heatmap_snapshot()
                
                # Merge adaptive risk info into cells
                risk_map = {r["cell_id"]: r for r in eval_res.get("cell_risks", [])}

                if role == "user":
                    # Strictly sanitized Public Heatmap - NO risk scores, NO confidence, simple Low/Moderate/Crowded status
                    sanitized_cells = []
                    for c in raw_cells:
                        cid = c["cell_id"]
                        r_info = risk_map.get(cid, {})
                        lvl = r_info.get("risk_level", "LOW")
                        c_status = "Crowded" if (lvl in ("HIGH", "CRITICAL") or c.get("density", 0) >= 10) else ("Moderate" if (lvl == "MEDIUM" or c.get("density", 0) >= 4) else "Low")
                        safe_alt = r_info.get("safe_alternative", "Nearby open area")
                        sanitized_cells.append({
                            "cell_id": cid,
                            "latitude": c["latitude"],
                            "longitude": c["longitude"],
                            "lat": c["latitude"],
                            "lon": c["longitude"],
                            "crowd_status": c_status,
                            "safe_guidance": "Normal pedestrian conditions" if c_status == "Low" else ("Moderate movement — follow signage" if c_status == "Moderate" else f"Busy area — recommended path via {safe_alt}"),
                            "safer_area": safe_alt if c_status == "Crowded" else None,
                            "last_updated": c.get("last_updated", _now_iso()),
                        })
                    payload = json.dumps({
                        "timestamp": _now_iso(),
                        "role": "user",
                        "demo_mode": False,
                        "cell_count": len(sanitized_cells),
                        "cells": sanitized_cells,
                    }).encode("utf-8")
                else:
                    # Full Manager Heatmap Intelligence with learned baselines, deviations, flows & trends
                    enriched_cells = []
                    for c in raw_cells:
                        cid = c["cell_id"]
                        r_info = risk_map.get(cid, {})
                        enriched_cells.append({
                            **c,
                            "risk_score": r_info.get("risk_score", 0.0),
                            "risk_level": r_info.get("risk_level", "LOW"),
                            "risk_cause": r_info.get("risk_cause", "Normal crowd conditions"),
                            "trend": r_info.get("trend", c.get("trend", "STABLE")),
                            "trend_delta": r_info.get("trend_delta", c.get("trend_delta", 0.0)),
                            "incoming_flow": r_info.get("incoming_flow", 0),
                            "outgoing_flow": r_info.get("outgoing_flow", 0),
                            "baseline_deviation": r_info.get("baseline_deviation", 0.0),
                        })
                    payload = json.dumps({
                        "timestamp": _now_iso(),
                        "role": "manager",
                        "demo_mode": False,
                        "cell_count": len(enriched_cells),
                        "cells": enriched_cells,
                    }).encode("utf-8")
            self._respond(200, payload)

        # --------------------------------------------------
        # GET /api/areas, /api/heatmap/threats, /api/threats - Unified Threat Model
        # --------------------------------------------------
        elif path in ("/api/areas", "/location/areas", "/areas", "/api/heatmap/threats", "/api/threats", "/threats"):
            if is_demo and dg:
                demo_data = dg.generate_heatmap_data(user_role=role)
                payload = json.dumps(demo_data["areas"]).encode("utf-8")
            else:
                eval_res = evaluate_location_risk_and_prevention(user_role=role)
                threats_list = eval_res.get("threats", [])
                payload = json.dumps({
                    "timestamp": _now_iso(),
                    "role": role,
                    "demo_mode": False,
                    "area_count": len(threats_list),
                    "areas": threats_list,
                }).encode("utf-8")
            self._respond(200, payload)

        # --------------------------------------------------
        # GET /api/flows (and /location/flows) - Aggregated cell flow
        # --------------------------------------------------
        elif path in ("/api/flows", "/location/flows", "/api/heatmap/flows"):
            if is_demo and dg:
                flows = [
                    {"source_cell": "18.5210_73.8570", "target_cell": "18.5200_73.8570", "flow": 18},
                    {"source_cell": "18.5190_73.8570", "target_cell": "18.5200_73.8570", "flow": 12},
                ]
            else:
                flows = get_aggregated_flows()
            payload = json.dumps({
                "timestamp": _now_iso(),
                "demo_mode": is_demo,
                "flow_count": len(flows),
                "flows": flows,
            }).encode("utf-8")
            self._respond(200, payload)

        # --------------------------------------------------
        # GET /api/heatmap/cell/{cell_id}
        # --------------------------------------------------
        elif path.startswith("/api/heatmap/cell/") or path.startswith("/location/heatmap/cell/"):
            prefix = "/api/heatmap/cell/" if path.startswith("/api/heatmap/cell/") else "/location/heatmap/cell/"
            raw_cell_id = path[len(prefix):]

            if not raw_cell_id or not _CELL_ID_RE.match(raw_cell_id):
                self._error(404, f"cell '{raw_cell_id}' not found")
                return

            if is_demo and dg:
                demo_data = dg.generate_heatmap_data(user_role=role)
                found = next((c for c in demo_data["heatmap"]["cells"] if c["cell_id"] == raw_cell_id), None)
                if found is None:
                    self._error(404, f"cell '{raw_cell_id}' not found")
                    return
                self._respond(200, json.dumps(found).encode("utf-8"))
            else:
                cell = get_cell(raw_cell_id)
                if cell is None:
                    self._error(404, f"cell '{raw_cell_id}' not found or has insufficient data")
                    return
                eval_res = evaluate_location_risk_and_prevention(user_role=role)
                r_info = next((r for r in eval_res.get("cell_risks", []) if r["cell_id"] == raw_cell_id), {})

                if role == "user":
                    lvl = r_info.get("risk_level", "LOW")
                    d = cell.get("density", 0)
                    c_status = "Crowded" if (lvl in ("HIGH", "CRITICAL") or d >= 10) else ("Moderate" if (lvl == "MEDIUM" or d >= 4) else "Low")
                    safe_alt = r_info.get("safe_alternative", "Nearby open ground")
                    sanitized_cell = {
                        "cell_id": cell["cell_id"],
                        "latitude": cell["latitude"],
                        "longitude": cell["longitude"],
                        "crowd_status": c_status,
                        "safe_guidance": "Normal conditions" if c_status == "Low" else ("Follow pedestrian signs for smooth passage" if c_status == "Moderate" else f"Busy area — proceed via {safe_alt}"),
                        "safer_area": safe_alt if c_status == "Crowded" else None,
                        "last_updated": cell.get("last_updated"),
                    }
                    self._respond(200, json.dumps(sanitized_cell).encode("utf-8"))
                else:
                    enriched = {
                        **cell,
                        "risk_score": r_info.get("risk_score", 0.0),
                        "risk_level": r_info.get("risk_level", "LOW"),
                        "risk_cause": r_info.get("risk_cause", "Normal crowd conditions"),
                        "trend": r_info.get("trend", cell.get("trend", "STABLE")),
                        "trend_delta": r_info.get("trend_delta", cell.get("trend_delta", 0.0)),
                        "incoming_flow": r_info.get("incoming_flow", 0),
                        "outgoing_flow": r_info.get("outgoing_flow", 0),
                        "baseline_deviation": r_info.get("baseline_deviation", 0.0),
                    }
                    self._respond(200, json.dumps(enriched).encode("utf-8"))

        # --------------------------------------------------
        # GET /api/location/status (and /location/status)
        # --------------------------------------------------
        elif path in ("/api/location/status", "/location/status"):
            if is_demo and dg:
                demo_data = dg.generate_heatmap_data(user_role=role)
                status = demo_data["status"]
            else:
                status = get_status()
                status["status"] = "active"
                status["demo_mode"] = False
                status["timestamp"] = _now_iso()
            self._respond(200, json.dumps(status).encode("utf-8"))

        else:
            self._error(404, "endpoint not found")

    def do_POST(self):
        dg = get_demo_generator()
        path = self.path.split("?")[0].rstrip("/")

        # --------------------------------------------------
        # POST /api/demo/toggle (or /location/demo/toggle)
        # --------------------------------------------------
        if path in ("/api/demo/toggle", "/demo/toggle", "/location/demo/toggle", "/api/location/demo/toggle"):
            length = int(self.headers.get("Content-Length", 0))
            body = {}
            if length > 0:
                try:
                    body = json.loads(self.rfile.read(length))
                except Exception:
                    body = {}
            if dg:
                enabled = body.get("enabled")
                state = dg.toggle_heatmap(enabled)
                scenario = body.get("scenario")
                if scenario:
                    dg.set_scenario(scenario)
                payload = {
                    "status": "ok",
                    "demo_mode": state,
                    "demo_scenario": dg.scenario,
                    "target": "heatmap",
                }
            else:
                payload = {"status": "error", "message": "Demo generator not available"}

            self._respond(200, json.dumps(payload).encode("utf-8"))
            return

        # --------------------------------------------------
        # POST /api/demo/scenario (or /location/demo/scenario)
        # --------------------------------------------------
        elif path in ("/api/demo/scenario", "/demo/scenario", "/location/demo/scenario"):
            length = int(self.headers.get("Content-Length", 0))
            body = {}
            if length > 0:
                try:
                    body = json.loads(self.rfile.read(length))
                except Exception:
                    body = {}
            scenario = body.get("scenario", "buildup")
            if dg:
                curr = dg.set_scenario(scenario)
                payload = {"status": "ok", "demo_scenario": curr}
            else:
                payload = {"status": "error", "message": "Demo generator not available"}

            self._respond(200, json.dumps(payload).encode("utf-8"))
            return

        # --------------------------------------------------
        # POST /api/location/reset (and /location/reset)
        # --------------------------------------------------
        elif path in ("/api/location/reset", "/location/reset"):
            from location_aggregator import reset_state
            reset_state()
            self._respond(200, json.dumps({"status": "ok", "message": "Location state reset"}).encode("utf-8"))
            return

        # --------------------------------------------------
        # POST /api/location/update (and /location/update)
        # --------------------------------------------------
        elif path in ("/api/location/update", "/location/update"):
            # Read body
            try:
                length = int(self.headers.get("Content-Length", 0))
                if length == 0:
                    self._error(400, "request body is required")
                    return
                raw_body = self.rfile.read(length)
                data = json.loads(raw_body)
            except json.JSONDecodeError as exc:
                self._error(400, f"malformed JSON: {exc}")
                return
            except Exception as exc:
                self._error(400, f"could not read request: {exc}")
                return

            if not isinstance(data, dict):
                self._error(400, "request body must be a JSON object")
                return

            # Validate fields
            try:
                lat = _validate_latitude(data.get("latitude") if "latitude" in data else data.get("lat"))
                lon = _validate_longitude(data.get("longitude") if "longitude" in data else data.get("lon"))
                _validate_timestamp(data.get("timestamp"))
                session_id = _validate_session_id(data.get("session_id"))
            except ValidationError as exc:
                self._error(400, str(exc))
                return

            # Ingest location signal
            try:
                cell = ingest_location(lat, lon, session_id)
            except Exception as exc:
                self._error(500, f"internal error: {exc}")
                return

            payload = json.dumps({
                "status": "accepted",
                "cell": cell,
            }).encode("utf-8")
            self._respond(200, payload)

        else:
            self._error(404, "endpoint not found")

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------

    def _respond(self, code: int, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code: int, message: str) -> None:
        body = json.dumps({"error": message}).encode("utf-8")
        self._respond(code, body)

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format, *args):
        # Suppress default per-request logging; use our own print statements.
        return


# =====================================================
# HELPERS
# =====================================================

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


# =====================================================
# ENTRY POINT
# =====================================================

if __name__ == "__main__":
    # Start background cleanup thread
    _cleanup_thread.start()

    server = ThreadingHTTPServer((HOST, PORT), LocationHandler)
    server.daemon_threads = True

    print("=" * 53)
    print(" CrowdShield - Location Server")
    print("=" * 53)
    print(f" Listening on: http://{HOST}:{PORT}")
    print()
    print(" Part 1 - Location Data Infrastructure:")
    print("   POST /api/location/update   -- ingest location signal")
    print("   GET  /api/location/status   -- server health")
    print()
    print(" Part 2 - Heatmap API:")
    print("   GET  /api/heatmap                    -- all active cells")
    print("   GET  /api/heatmap/cell/{cell_id}     -- single cell details")
    print()
    print(f" Privacy: coordinates snapped to ~{int(GRID_STEP*111000)} m grid")
    print(f"          session IDs SHA-256 hashed")
    print(f"          sessions expire after {SESSION_STALE_SECONDS}s of silence")
    print(f"          density = unique active sessions, not request count")
    print()
    print(" Camera server is UNAFFECTED (port 8765)")
    print(" Press Ctrl+C to stop.")
    print("=" * 53)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[location_server] Shutting down.")
