"""
CrowdShield — Location Aggregation Engine
==========================================
Pure-Python, thread-safe data layer for geographic cell aggregation.

Responsibilities
----------------
- Accept opt-in location signals (latitude, longitude, session_id, timestamp)
- Snap raw coordinates to a coarse grid (~0.001 degrees approx 111 m per degree at equator)
- Maintain lightweight per-session state to avoid double-counting
- Maintain per-cell crowd density as unique active sessions, NOT request count
- Expire stale sessions automatically
- Expose aggregated cell snapshots for the API layer

Privacy design
--------------
- Individual coordinates are NEVER stored after grid-snapping.
- Session IDs are one-way hashed (SHA-256, truncated) - raw IDs never persisted.
- Density = unique active sessions per cell, NOT total requests.
- No trajectories, no movement history.
- Cells are coarse (~111 m), so individual positions cannot be inferred.
"""

from __future__ import annotations

import hashlib
import os
import sys
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# Import shared risk & prevention engine
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, ".."))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from risk_engine import (
    AdaptiveBaseline,
    calculate_adaptive_risk,
    identify_risk_cause,
    select_safe_alternative_area,
    generate_action_string,
    compute_trend,
    TREND_THRESHOLD,
)

# =====================================================
# CONFIGURATION
# =====================================================

# Grid resolution in degrees. 0.001 deg approx 111 m at the equator.
GRID_STEP: float = 0.001

# A session is considered active if we received an update within this window.
SESSION_ACTIVE_SECONDS: int = 5 * 60   # 5 minutes

# A session is considered stale (removed) after this period of silence.
SESSION_STALE_SECONDS: int = 7 * 60    # 7 minutes

# Confidence denominator: a cell with this many unique sessions is "fully confident" (confidence -> 1.0).
CONFIDENCE_FULL_SESSIONS: int = 20

# Minimum unique sessions before a cell is exposed in the heatmap snapshot.
MIN_SESSIONS_TO_EXPOSE: int = 2


# =====================================================
# DATA MODELS
# =====================================================

@dataclass
class SessionState:
    """Lightweight per-session record. No trajectory, no raw coordinates."""
    hashed_id: str
    current_cell: str           # cell_id the session was last seen in
    last_seen: float            # UTC Unix timestamp of last update
    is_active: bool = True


@dataclass
class CellState:
    """Aggregated crowd state and adaptive risk profile for one geographic cell."""
    cell_id: str
    lat_center: float
    lon_center: float
    active_sessions: int = 0
    last_updated: float = 0.0   # UTC Unix timestamp
    
    # History & Adaptive Baseline (Part 3)
    density_history: deque = field(default_factory=lambda: deque(maxlen=20))
    baseline: AdaptiveBaseline = field(default_factory=lambda: AdaptiveBaseline(min_samples=6, window_size=60))
    incoming_baseline: AdaptiveBaseline = field(default_factory=lambda: AdaptiveBaseline(min_samples=6, window_size=60))
    outgoing_baseline: AdaptiveBaseline = field(default_factory=lambda: AdaptiveBaseline(min_samples=6, window_size=60))
    
    # Flow tracking (aggregated counts within current active window)
    incoming_flow: int = 0
    outgoing_flow: int = 0

    def density(self) -> int:
        """Density = number of unique active sessions currently in this cell."""
        return self.active_sessions

    def confidence(self) -> float:
        """
        Confidence in the density reading [0.0, 1.0].
        Increases with more active sessions, capped at 1.0.
        """
        if self.active_sessions == 0:
            return 0.0
        return min(self.active_sessions / CONFIDENCE_FULL_SESSIONS, 1.0)

    def compute_trend_info(self) -> tuple[str, float]:
        """Calculates (RISING / FALLING / STABLE, delta) using recent density history."""
        hist = list(self.density_history)
        if len(hist) < 4:
            # If history is short, compare current density to history start
            if len(hist) >= 2:
                delta = hist[-1] - hist[0]
                if delta > 0.5:
                    return "RISING", round(float(delta), 2)
                elif delta < -0.5:
                    return "FALLING", round(float(delta), 2)
            return "STABLE", 0.0
        return compute_trend(hist)

    def as_dict(self) -> dict:
        trend, delta = self.compute_trend_info()
        return {
            "cell_id": self.cell_id,
            "latitude": self.lat_center,
            "longitude": self.lon_center,
            "lat": self.lat_center,
            "lon": self.lon_center,
            "density": self.active_sessions,
            "active_sessions": self.active_sessions,
            "confidence": round(self.confidence(), 3),
            "trend": trend,
            "trend_delta": round(delta, 2),
            "incoming_flow": self.incoming_flow,
            "outgoing_flow": self.outgoing_flow,
            "last_updated": _ts_to_iso(self.last_updated),
        }


# =====================================================
# MODULE-LEVEL STATE (thread-safe)
# =====================================================

_lock = threading.Lock()

# hashed_session_id -> SessionState
_sessions: dict[str, SessionState] = {}

# cell_id -> CellState
_cells: dict[str, CellState] = {}

# Aggregated pairwise transition flow between cells: (source_cell_id, target_cell_id) -> count
_cell_flows: dict[tuple[str, str], int] = {}


# =====================================================
# HELPERS
# =====================================================

def _utc_now() -> float:
    return datetime.now(timezone.utc).timestamp()


def _ts_to_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def snap_to_grid(lat: float, lon: float) -> tuple:
    """Quantise coordinates to the nearest grid cell centre."""
    snapped_lat = round(round(lat / GRID_STEP) * GRID_STEP, 6)
    snapped_lon = round(round(lon / GRID_STEP) * GRID_STEP, 6)
    return snapped_lat, snapped_lon


def cell_id_for(lat: float, lon: float) -> str:
    """Return a stable, deterministic identifier for a grid cell."""
    slat, slon = snap_to_grid(lat, lon)
    return f"{slat:.4f}_{slon:.4f}"


def _hash_session(raw_id: str) -> str:
    """One-way hash of a raw session ID. Never store the original."""
    return hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:20]


def _get_or_create_cell(cell_id: str, lat: float, lon: float) -> CellState:
    """Return existing cell or create a new one. Must be called under _lock."""
    if cell_id not in _cells:
        slat, slon = snap_to_grid(lat, lon)
        _cells[cell_id] = CellState(
            cell_id=cell_id,
            lat_center=slat,
            lon_center=slon,
            last_updated=_utc_now(),
        )
    return _cells[cell_id]


def _recount_cell(cell_id: str) -> None:
    """
    Recompute active_sessions for a cell from live session states.
    Updates rolling density history and adaptive baselines.
    Must be called under _lock.
    """
    if cell_id not in _cells:
        return
    now = _utc_now()
    count = sum(
        1 for s in _sessions.values()
        if s.current_cell == cell_id
        and s.is_active
        and (now - s.last_seen) <= SESSION_ACTIVE_SECONDS
    )
    cell = _cells[cell_id]
    cell.active_sessions = count
    cell.last_updated = now

    # Update density history buffer
    cell.density_history.append(float(count))

    # Update adaptive baseline
    cell.baseline.update(float(count))
    cell.incoming_baseline.update(float(cell.incoming_flow))
    cell.outgoing_baseline.update(float(cell.outgoing_flow))


# =====================================================
# PUBLIC API
# =====================================================

def ingest_location(lat: float, lon: float, session_id: str) -> dict:
    """
    Accept one location signal. Returns the updated cell summary dict.

    Privacy guarantees:
    - lat/lon are snapped to the grid immediately.
    - session_id is hashed before storage.
    - No raw coordinates or raw session IDs are stored.
    - Individual trajectories are NEVER retained.
    - Aggregated pairwise transition flow between cells is tracked anonymously.
    """
    hashed = _hash_session(session_id)
    new_cell_id = cell_id_for(lat, lon)
    now = _utc_now()

    with _lock:
        if hashed in _sessions:
            sess = _sessions[hashed]
            old_cell_id = sess.current_cell

            if old_cell_id != new_cell_id:
                # Session moved between cells:
                # 1. Update aggregate transition flow (source -> target)
                flow_key = (old_cell_id, new_cell_id)
                _cell_flows[flow_key] = _cell_flows.get(flow_key, 0) + 1

                # 2. Update incoming/outgoing counters on affected cells
                if old_cell_id in _cells:
                    _cells[old_cell_id].outgoing_flow += 1
                _get_or_create_cell(new_cell_id, lat, lon)
                _cells[new_cell_id].incoming_flow += 1

                # 3. Update session position
                sess.current_cell = new_cell_id
                sess.last_seen = now
                sess.is_active = True

                _recount_cell(old_cell_id)
            else:
                # Same cell: update timestamp only (no double-count)
                sess.last_seen = now
                sess.is_active = True
        else:
            # New session entering the system
            _sessions[hashed] = SessionState(
                hashed_id=hashed,
                current_cell=new_cell_id,
                last_seen=now,
                is_active=True,
            )

        # Ensure cell exists and recount
        _get_or_create_cell(new_cell_id, lat, lon)
        _recount_cell(new_cell_id)

        cell = _cells[new_cell_id]
        return cell.as_dict()


def cleanup_stale_sessions() -> int:
    """
    Remove sessions that have been silent beyond SESSION_STALE_SECONDS.
    Recount affected cells after removal.
    Returns the number of sessions removed.
    """
    now = _utc_now()
    stale_threshold = now - SESSION_STALE_SECONDS

    with _lock:
        stale_ids = [
            hid for hid, s in _sessions.items()
            if s.last_seen < stale_threshold
        ]
        affected_cells: set = set()
        for hid in stale_ids:
            affected_cells.add(_sessions[hid].current_cell)
            del _sessions[hid]

        for cell_id in affected_cells:
            _recount_cell(cell_id)

        # Remove cells that are now empty
        empty_cells = [cid for cid, c in _cells.items() if c.active_sessions == 0]
        for cid in empty_cells:
            del _cells[cid]

    return len(stale_ids)


def get_heatmap_snapshot() -> list:
    """
    Return a list of all cells with at least MIN_SESSIONS_TO_EXPOSE unique active sessions.
    Sorted by density descending.
    """
    with _lock:
        result = [
            cell.as_dict()
            for cell in _cells.values()
            if cell.active_sessions >= MIN_SESSIONS_TO_EXPOSE
        ]

    result.sort(key=lambda c: c["density"], reverse=True)
    return result


def get_cell(cell_id: str) -> Optional[dict]:
    """
    Return the cell dict for a given cell_id, or None if it does not exist
    or has fewer than MIN_SESSIONS_TO_EXPOSE active sessions.
    """
    with _lock:
        cell = _cells.get(cell_id)
        if cell is None or cell.active_sessions < MIN_SESSIONS_TO_EXPOSE:
            return None
        return cell.as_dict()


def get_status() -> dict:
    """Return a high-level status dict (no individual data exposed)."""
    with _lock:
        total_cells = len(_cells)
        total_sessions = len(_sessions)
        visible_cells = sum(
            1 for c in _cells.values()
            if c.active_sessions >= MIN_SESSIONS_TO_EXPOSE
        )

    return {
        "total_cells": total_cells,
        "visible_cells": visible_cells,
        "active_sessions": total_sessions,
        "session_timeout_seconds": SESSION_STALE_SECONDS,
        "grid_step_degrees": GRID_STEP,
        "grid_step_meters_approx": int(GRID_STEP * 111000),
    }


def get_aggregated_flows() -> list[dict]:
    """
    Returns aggregate anonymous flow between neighbouring cells.
    Format: [{"source_cell": "...", "target_cell": "...", "flow": 18}]
    """
    with _lock:
        return [
            {"source_cell": src, "target_cell": tgt, "flow": count}
            for (src, tgt), count in _cell_flows.items()
            if count > 0
        ]


def reset_state() -> None:
    """Reset all in-memory sessions, cells, and flows (thread-safe)."""
    with _lock:
        _sessions.clear()
        _cells.clear()
        _cell_flows.clear()


# =====================================================
# PART 3: RISK, ORIGIN & PREVENTION EVALUATION
# =====================================================

def evaluate_location_risk_and_prevention(user_role: str = "manager") -> dict:
    """
    Runs the existing Shared Risk & Prevention Engine on all live geographic cells.
    Detects early warnings, performs origin analysis, selects safe alternatives,
    and formats threats into the Unified Threat Model.
    """
    with _lock:
        cells_list = [c for c in _cells.values() if c.active_sessions >= 1]
        flows_copy = dict(_cell_flows)

    # 1. Compute per-cell risk metrics using shared Risk Engine
    cell_risks = []
    for cell in cells_list:
        density = float(cell.active_sessions)
        trend, delta = cell.compute_trend_info()

        d_change = max(delta, 0.0)
        density_dev = cell.baseline.deviation(density)
        inc_dev = cell.incoming_baseline.deviation(float(cell.incoming_flow))
        out_dev = cell.outgoing_baseline.deviation(float(cell.outgoing_flow))
        d_std = cell.baseline.std if cell.baseline.std is not None else 1.0

        risk_score, risk_lvl = calculate_adaptive_risk(
            density=density,
            density_change=d_change,
            incoming=float(cell.incoming_flow),
            outgoing=float(cell.outgoing_flow),
            density_deviation=density_dev,
            incoming_deviation=inc_dev,
            outgoing_deviation=out_dev,
            density_std=d_std,
        )

        cause = identify_risk_cause(
            density=density,
            density_change=d_change,
            incoming=float(cell.incoming_flow),
            outgoing=float(cell.outgoing_flow),
            density_deviation=density_dev,
            incoming_deviation=inc_dev,
        )

        cell_risks.append({
            "cell": cell,
            "cell_id": cell.cell_id,
            "density": int(density),
            "trend": trend,
            "trend_delta": delta,
            "risk_score": round(float(risk_score), 1),
            "risk_level": risk_lvl,
            "risk_cause": cause,
            "incoming_flow": cell.incoming_flow,
            "outgoing_flow": cell.outgoing_flow,
            "baseline_deviation": round(density_dev, 2),
        })

    # 2. Location-Based Origin Analysis & Dynamic Safe Alternative Selection
    threats = []
    candidate_areas = [
        {"area_id": r["cell_id"], "risk_score": r["risk_score"], "density": r["density"], "trend": r["trend"]}
        for r in cell_risks
    ]

    for item in cell_risks:
        lvl = item["risk_level"]
        target_cell_id = item["cell_id"]

        # Origin Analysis: find upstream cell with maximum incoming flow
        best_origin = None
        max_flow = 0
        for (src, tgt), count in flows_copy.items():
            if tgt == target_cell_id and count > max_flow:
                max_flow = count
                best_origin = src

        origin_str = best_origin if (best_origin and max_flow >= 1) else "UNKNOWN"

        # Dynamic Safe Alternative Selection
        safe_alt = select_safe_alternative_area(target_cell_id, best_origin, candidate_areas) or "Nearby open area"
        action = generate_action_string(lvl, target_cell_id, safe_alt)

        # Public non-alarming transformation
        if lvl == "CRITICAL":
            crowd_status = "Crowded"
            user_action = f"High foot-traffic in {target_cell_id}. Recommended alternate path: {safe_alt}."
            safety_instruction = f"Proceed calmly toward {safe_alt}."
        elif lvl == "HIGH":
            crowd_status = "Moderate"
            user_action = f"Moderate movement in {target_cell_id}. Clearer walking route via {safe_alt}."
            safety_instruction = f"Follow directional signs toward {safe_alt}."
        elif lvl == "MEDIUM":
            crowd_status = "Moderate"
            user_action = f"Moderate crowd in {target_cell_id}. Clear paths available."
            safety_instruction = "Maintain regular walking pace."
        else:
            crowd_status = "Low"
            user_action = f"Clear passage at {target_cell_id}."
            safety_instruction = "Open pathways available."

        # Unified Threat Model object
        if user_role == "manager":
            threat_item = {
                "source": "location",
                "area": target_cell_id,
                "cell_id": target_cell_id,
                "density": item["density"],
                "risk_score": item["risk_score"],
                "risk_level": lvl,
                "trend": item["trend"],
                "trend_delta": item["trend_delta"],
                "risk_cause": item["risk_cause"],
                "possible_origin": origin_str,
                "flow_from_origin": max_flow if origin_str != "UNKNOWN" else 0,
                "safe_alternative": safe_alt,
                "recommended_action": action,
            }
        else:
            threat_item = {
                "source": "location",
                "area": target_cell_id,
                "cell_id": target_cell_id,
                "crowd_status": crowd_status,
                "safe_alternative": safe_alt,
                "recommended_route": f"Use {safe_alt} for less congestion",
                "safe_guidance": user_action,
                "safety_instruction": safety_instruction,
                "recommended_action": user_action,
            }

        # Include in threats list if elevated risk or if query requested
        if lvl in ("MEDIUM", "HIGH", "CRITICAL") or item["density"] >= 5:
            threats.append(threat_item)

    if user_role == "manager":
        threats.sort(key=lambda t: t.get("risk_score", 0.0), reverse=True)
    else:
        severity_order = {"Crowded": 3, "Moderate": 2, "Low": 1}
        threats.sort(key=lambda t: severity_order.get(t.get("crowd_status"), 0), reverse=True)

    return {
        "threats": threats,
        "cell_risks": cell_risks,
        "flows": get_aggregated_flows(),
    }
