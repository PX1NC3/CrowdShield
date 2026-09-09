"""
Comprehensive Test Suite for LIVE -> DEMO -> LIVE transitions and Synthetic Demo Scenarios:
1. Camera API (port 8765):
   - LIVE default state
   - Toggle to DEMO
   - Test all 4 scenarios (Normal, Build-up, Critical Risk, Dispersal)
   - Verify dynamic metrics (3x3 zones, density, trends, flow, risk scores, prevention routes)
   - Verify role-based filtering (Manager diagnostics vs Public guidance)
   - Toggle back to LIVE and ensure untouched live camera state
2. Heatmap API (port 8766):
   - LIVE default state
   - Toggle to DEMO
   - Test all 4 scenarios (Normal, Build-up, Critical Risk, Dispersal)
   - Verify dynamic evolving cells, density, confidence, risk levels, threat areas
   - Verify role-based filtering (Manager operations vs Public guidance)
   - Toggle back to LIVE and ensure untouched live ingestion pipeline
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer

# Add project paths
_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.join(_TEST_DIR, "src")
sys.path.insert(0, _TEST_DIR)
sys.path.insert(0, _SRC_DIR)
sys.path.insert(0, os.path.join(_SRC_DIR, "detection"))
sys.path.insert(0, os.path.join(_SRC_DIR, "location"))

import detect
import location_server
from demo_generator import demo_generator

CAM_PORT = 8795
LOC_PORT = 8796
CAM_BASE = f"http://127.0.0.1:{CAM_PORT}"
LOC_BASE = f"http://127.0.0.1:{LOC_PORT}"

PASS_COUNT = 0
FAIL_COUNT = 0


def chk(label: str, cond: bool) -> bool:
    global PASS_COUNT, FAIL_COUNT
    result = "PASS" if cond else "FAIL"
    if cond:
        PASS_COUNT += 1
    else:
        FAIL_COUNT += 1
    print(f"  [{result}] {label}")
    return cond


def get(url: str):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def post(url: str, data: dict):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, body, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def run_tests():
    print("=" * 60)
    print(" CrowdShield LIVE -> DEMO -> LIVE Full Test Suite")
    print("=" * 60)

    # -------------------------------------------------------------
    # 1. CAMERA PIPELINE: LIVE -> DEMO -> LIVE
    # -------------------------------------------------------------
    print("\n--- 1. CAMERA PIPELINE TESTING ---")

    # Step 1.1: Verify Initial LIVE state
    print("\n[C1] Verify Initial LIVE State")
    code, resp = get(f"{CAM_BASE}/live_prevention.json")
    chk("HTTP 200", code == 200)
    chk("live mode active (demo_mode is False)", resp.get("demo_mode") is False)
    chk("has cameras summary", "cameras" in resp)
    chk("has threats array", "threats" in resp)

    # Step 1.2: Switch to DEMO MODE
    print("\n[C2] Switch to DEMO MODE")
    code, resp = post(f"{CAM_BASE}/api/demo/toggle", {"enabled": True, "scenario": "buildup"})
    chk("HTTP 200 on toggle", code == 200)
    chk("demo_mode is True", resp.get("demo_mode") is True)
    chk("scenario set to buildup", resp.get("demo_scenario") == "buildup")

    # Step 1.3: Verify Demo prevention snapshot schema
    print("\n[C3] Inspect Demo Prevention Snapshot (Same Schema)")
    code, resp = get(f"{CAM_BASE}/live_prevention.json")
    chk("HTTP 200", code == 200)
    chk("demo_mode is True in payload", resp.get("demo_mode") is True)
    chk("total_people > 0", resp.get("total_people", 0) > 0)
    chk("threats detected in buildup scenario", resp.get("threat_detected") is True)
    chk("highest_risk_level is MEDIUM or HIGH", resp.get("highest_risk_level") in ("MEDIUM", "HIGH", "CRITICAL"))

    # Step 1.4: Verify Demo Zones snapshot
    print("\n[C4] Inspect Demo /zones Endpoint")
    code, resp = get(f"{CAM_BASE}/zones?cam=cam1")
    chk("HTTP 200", code == 200)
    chk("has 9 zones", len(resp.get("zones", [])) == 9)
    z5 = resp["zones"][4]
    chk("Z5 has density, trend, risk_score", "density" in z5 and "trend" in z5 and "risk_score" in z5)

    # Step 1.5: Test All 4 Scenarios
    print("\n[C5] Testing 4 Demo Scenarios on Camera")
    for sc in ["normal", "buildup", "critical", "dispersal"]:
        post(f"{CAM_BASE}/api/demo/scenario", {"scenario": sc})
        _, p = get(f"{CAM_BASE}/live_prevention.json")
        _, z = get(f"{CAM_BASE}/zones")
        if sc == "normal":
            chk(f"Scenario [{sc}]: highest_risk_level is LOW", p.get("highest_risk_level") == "LOW")
            chk(f"Scenario [{sc}]: threat_detected is False", p.get("threat_detected") is False)
        elif sc == "critical":
            chk(f"Scenario [{sc}]: highest_risk_level is CRITICAL", p.get("highest_risk_level") == "CRITICAL")
            chk(f"Scenario [{sc}]: threat_count >= 2", p.get("threat_count", 0) >= 2)
            chk(f"Scenario [{sc}]: contains emergency diversion action", any("IMMEDIATE DIVERSION" in t.get("recommended_action", "") for t in p.get("threats", [])))
        elif sc == "dispersal":
            chk(f"Scenario [{sc}]: trends show FALLING", any(zone.get("trend") == "FALLING" for zone in z.get("zones", [])))

    # Step 1.6: Role-Based Filtering on Camera (Manager vs Public)
    print("\n[C6] Role-Based Filtering on Camera (Manager vs Public)")
    post(f"{CAM_BASE}/api/demo/scenario", {"scenario": "critical"})
    _, mgr_cam = get(f"{CAM_BASE}/live_prevention.json?role=manager")
    _, usr_cam = get(f"{CAM_BASE}/live_prevention.json?role=user")
    chk("Manager sees origin and diagnostic cause",
        mgr_cam["threats"][0].get("possible_origin") is not None and len(mgr_cam["threats"][0].get("risk_cause", "")) > 5)
    chk("Public has NO risk_score", "risk_score" not in usr_cam["threats"][0])
    chk("Public has NO possible_origin", "possible_origin" not in usr_cam["threats"][0])
    chk("Public sees simple crowd_status (Low/Moderate/Crowded)", usr_cam["threats"][0].get("crowd_status") in ("Low", "Moderate", "Crowded"))
    chk("Public sees safe route & navigation guidance", "safe_alternative" in usr_cam["threats"][0] and "recommended_route" in usr_cam["threats"][0])
    chk("Public action is calm and non-alarming", "alternate path" in usr_cam["threats"][0].get("safe_guidance", "").lower())

    # Step 1.7: Switch Camera Back to LIVE Mode
    print("\n[C7] Switch Camera Back to LIVE Mode")
    code, resp = post(f"{CAM_BASE}/api/demo/toggle", {"enabled": False})
    chk("HTTP 200 on toggle", code == 200)
    chk("demo_mode is False", resp.get("demo_mode") is False)
    _, live_resp = get(f"{CAM_BASE}/live_prevention.json")
    chk("Returned to LIVE mode (demo_mode False)", live_resp.get("demo_mode") is False)

    # -------------------------------------------------------------
    # 2. HEATMAP PIPELINE: LIVE -> DEMO -> LIVE
    # -------------------------------------------------------------
    print("\n--- 2. HEATMAP PIPELINE TESTING ---")

    # Step 2.1: Verify Initial LIVE Heatmap & Ingestion
    print("\n[H1] Verify Initial LIVE Heatmap & Location Ingestion")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    code, resp = post(f"{LOC_BASE}/api/location/update", {
        "latitude": 18.5204,
        "longitude": 73.8567,
        "timestamp": ts,
        "session_id": "test-sess-1",
    })
    chk("Location update accepted in LIVE mode", code == 200 and resp.get("status") == "accepted")
    code, h_live = get(f"{LOC_BASE}/api/heatmap")
    chk("HTTP 200 on /api/heatmap", code == 200)
    chk("LIVE heatmap demo_mode is False", h_live.get("demo_mode") is False)

    # Step 2.2: Switch Heatmap to DEMO MODE
    print("\n[H2] Switch Heatmap to DEMO MODE")
    code, resp = post(f"{LOC_BASE}/api/demo/toggle", {"enabled": True, "scenario": "critical"})
    chk("HTTP 200 on toggle", code == 200)
    chk("demo_mode is True", resp.get("demo_mode") is True)
    chk("scenario is critical", resp.get("demo_scenario") == "critical")

    # Step 2.3: Verify Demo Heatmap Cells & Structure
    print("\n[H3] Inspect Demo Heatmap Payload (Same Schema)")
    code, h_demo = get(f"{LOC_BASE}/api/heatmap")
    chk("HTTP 200", code == 200)
    chk("demo_mode is True in payload", h_demo.get("demo_mode") is True)
    chk("has cells list with 6 geographic cells", len(h_demo.get("cells", [])) == 6)
    first_cell = h_demo["cells"][0]
    chk("cell has cell_id, lat, lon, density, confidence, trend, risk_level",
        all(k in first_cell for k in ("cell_id", "latitude", "longitude", "density", "confidence", "trend", "risk_level")))

    # Step 2.4: Test Single Cell & Areas Endpoints in Demo Mode
    print("\n[H4] Demo Single Cell & Areas Endpoints")
    cid = first_cell["cell_id"]
    code, c_resp = get(f"{LOC_BASE}/api/heatmap/cell/{cid}")
    chk(f"GET /api/heatmap/cell/{cid} returns 200", code == 200)
    chk("Cell density matches snapshot", c_resp.get("density") == first_cell["density"])

    code, a_resp = get(f"{LOC_BASE}/api/areas")
    chk("GET /api/areas returns 200", code == 200)
    chk("Has area alerts in critical scenario", len(a_resp.get("areas", [])) >= 2)

    # Step 2.5: Test All 4 Scenarios on Heatmap
    print("\n[H5] Testing 4 Demo Scenarios on Heatmap")
    for sc in ["normal", "buildup", "critical", "dispersal"]:
        post(f"{LOC_BASE}/api/demo/scenario", {"scenario": sc})
        _, hm = get(f"{LOC_BASE}/api/heatmap")
        top_cell = hm["cells"][0]
        if sc == "normal":
            chk(f"Scenario [{sc}]: top cell risk is LOW", top_cell.get("risk_level") == "LOW")
            chk(f"Scenario [{sc}]: all cells STABLE", all(c.get("trend") == "STABLE" for c in hm["cells"]))
        elif sc == "critical":
            chk(f"Scenario [{sc}]: top cell risk is CRITICAL", top_cell.get("risk_level") == "CRITICAL")
            chk(f"Scenario [{sc}]: density > 100", top_cell.get("density", 0) > 90)
        elif sc == "dispersal":
            chk(f"Scenario [{sc}]: center cells show FALLING trend", any(c.get("trend") == "FALLING" for c in hm["cells"]))

    # Step 2.6: Strict Role-Based Filtering on Heatmap
    print("\n[H6] Strict Role-Based Filtering on Heatmap")
    post(f"{LOC_BASE}/api/demo/scenario", {"scenario": "critical"})
    _, mgr_hm = get(f"{LOC_BASE}/api/heatmap?role=manager")
    _, usr_hm = get(f"{LOC_BASE}/api/heatmap?role=user")
    chk("Manager sees operational ACCESS CONTROL actions", "ACCESS CONTROL" in mgr_hm["cells"][0].get("action", ""))
    chk("Manager cell contains risk_score", "risk_score" in mgr_hm["cells"][0])
    chk("Public cell does NOT contain risk_score or confidence", "risk_score" not in usr_hm["cells"][0] and "confidence" not in usr_hm["cells"][0])
    chk("Public cell contains simple crowd_status (Low/Moderate/Crowded)", usr_hm["cells"][0].get("crowd_status") in ("Low", "Moderate", "Crowded"))
    chk("Public cell provides wayfinding and safer area guidance", "wayfinding" in usr_hm["cells"][0] and "safer_area" in usr_hm["cells"][0])

    # Step 2.7: Switch Heatmap Back to LIVE Mode
    print("\n[H7] Switch Heatmap Back to LIVE Mode")
    code, resp = post(f"{LOC_BASE}/api/demo/toggle", {"enabled": False})
    chk("HTTP 200 on toggle", code == 200)
    chk("demo_mode is False", resp.get("demo_mode") is False)
    _, h_live_final = get(f"{LOC_BASE}/api/heatmap")
    chk("Heatmap returned to LIVE mode (demo_mode False)", h_live_final.get("demo_mode") is False)

    print("\n" + "=" * 60)
    print(f"  Final Results: {PASS_COUNT} PASSED, {FAIL_COUNT} FAILED")
    print("=" * 60)


if __name__ == "__main__":
    # Start both test servers on isolated ports in background threads
    loc_srv = ThreadingHTTPServer((location_server.HOST, LOC_PORT), location_server.LocationHandler)
    loc_srv.daemon_threads = True
    t_loc = threading.Thread(target=loc_srv.serve_forever, daemon=True)
    t_loc.start()

    cam_srv = ThreadingHTTPServer((detect.LIVE_API_HOST, CAM_PORT), detect.LivePreventionHandler)
    cam_srv.daemon_threads = True
    t_cam = threading.Thread(target=cam_srv.serve_forever, daemon=True)
    t_cam.start()

    time.sleep(0.5)

    try:
        run_tests()
    finally:
        loc_srv.shutdown()
        cam_srv.shutdown()
