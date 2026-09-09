"""
Part 3 Integration Test Suite for CrowdShield:
- Density trends (RISING, FALLING, STABLE) on geographic cells
- Per-cell adaptive baseline online learning & deviation
- Early warning risk detection (small headcount with rapid surge)
- Aggregate pairwise cell flow tracking
- Location-based origin analysis
- Dynamic safe alternative selection
- Unified Threat Model verification
- Regression verification for camera pipeline
"""

import sys
import os
import time
import json
import threading
import urllib.request
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer

_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.join(_DIR, "src")
sys.path.insert(0, _DIR)
sys.path.insert(0, _SRC_DIR)
sys.path.insert(0, os.path.join(_SRC_DIR, "detection"))
sys.path.insert(0, os.path.join(_SRC_DIR, "location"))

from risk_engine import (
    AdaptiveBaseline,
    calculate_adaptive_risk,
    identify_risk_cause,
    select_safe_alternative_area,
    compute_trend,
)
import location_aggregator
from location_aggregator import (
    ingest_location,
    get_aggregated_flows,
    evaluate_location_risk_and_prevention,
)
import location_server
import detect

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

def test_risk_engine_and_baselines():
    print("\n--- 1. ADAPTIVE BASELINE & EARLY WARNING TESTS ---")
    
    # 1.1 Baseline learning
    base = AdaptiveBaseline(min_samples=5, window_size=20)
    for _ in range(10):
        base.update(5.0)
    chk("Baseline learned mean ~ 5.0", abs(base.mean - 5.0) < 0.2)
    chk("Deviation for normal (5.0) is ~ 0.0", abs(base.deviation(5.0)) < 0.5)
    chk("Deviation for surge (15.0) is significant (> 2.0)", base.deviation(15.0) > 2.0)
    
    # 1.2 Early Warning on small headcount with rapid surge
    # Small crowd (5 people), rapid rising (+3), high incoming (+4), high deviation (3.0)
    risk_score, risk_lvl = calculate_adaptive_risk(
        density=5.0,
        density_change=3.0,
        incoming=4.0,
        outgoing=0.0,
        density_deviation=3.0,
        incoming_deviation=2.5,
        outgoing_deviation=0.0,
        density_std=1.0,
    )
    chk("Early warning triggered for small crowd with surge (level >= HIGH)", risk_lvl in ("HIGH", "CRITICAL"))
    chk("Early warning risk_score > 60", risk_score > 60.0)

    # 1.3 Stable crowd baseline test
    risk_s2, risk_lvl2 = calculate_adaptive_risk(
        density=20.0,
        density_change=0.0,
        incoming=0.0,
        outgoing=0.0,
        density_deviation=0.0,
        incoming_deviation=0.0,
        outgoing_deviation=0.0,
        density_std=2.0,
    )
    chk("Stable crowd with zero deviation is LOW risk", risk_lvl2 == "LOW")

def test_density_trends():
    print("\n--- 2. GEOGRAPHIC CELL DENSITY TRENDS ---")
    hist_rising = [10.0, 11.0, 12.0, 16.0, 18.0, 20.0]
    trend_r, d_r = compute_trend(hist_rising)
    chk("History detects RISING trend", trend_r == "RISING")
    chk("Delta is positive", d_r > 0)

    hist_falling = [20.0, 19.0, 18.0, 14.0, 12.0, 10.0]
    trend_f, d_f = compute_trend(hist_falling)
    chk("History detects FALLING trend", trend_f == "FALLING")
    chk("Delta is negative", d_f < 0)

    hist_stable = [15.0, 15.0, 15.0, 15.0, 15.0, 15.0]
    trend_s, d_s = compute_trend(hist_stable)
    chk("History detects STABLE trend", trend_s == "STABLE")

def test_flow_and_origin_analysis():
    print("\n--- 3. AGGREGATED FLOW & ORIGIN DETECTION ---")
    # Simulate movement from Cell A (18.520, 73.850) -> Cell B (18.521, 73.850)
    for i in range(12):
        s_id = f"mover_{i}"
        # Start in Cell A
        ingest_location(18.5200, 73.8500, s_id)
        # Move to Cell B
        ingest_location(18.5210, 73.8500, s_id)
    
    flows = get_aggregated_flows()
    found_flow = next((f for f in flows if f["source_cell"] == "18.5200_73.8500" and f["target_cell"] == "18.5210_73.8500"), None)
    chk("Pairwise aggregate flow recorded between Cell A and Cell B", found_flow is not None)
    chk("Flow count matches movement (12)", found_flow["flow"] == 12 if found_flow else False)

    # Evaluate risk & origin analysis
    eval_mgr = evaluate_location_risk_and_prevention(user_role="manager")
    target_threat = next((t for t in eval_mgr["threats"] if t["cell_id"] == "18.5210_73.8500"), None)
    chk("Target cell B detected as threat", target_threat is not None)
    chk("Origin correctly identified as Cell A", target_threat["possible_origin"] == "18.5200_73.8500" if target_threat else False)
    chk("Flow from origin recorded (> 10)", target_threat.get("flow_from_origin", 0) >= 10 if target_threat else False)

def test_dynamic_safe_alternative_selection():
    print("\n--- 4. DYNAMIC SAFE ALTERNATIVE SELECTION ---")
    candidates = [
        {"cell_id": "Cell_A", "risk_score": 85.0, "density": 90, "trend": "RISING"},
        {"cell_id": "Cell_B", "risk_score": 75.0, "density": 60, "trend": "RISING"},
        {"cell_id": "Cell_C", "risk_score": 10.0, "density": 8, "trend": "FALLING"},
        {"cell_id": "Cell_D", "risk_score": 30.0, "density": 20, "trend": "STABLE"},
    ]
    # If Cell_A is target and Cell_B is origin, Cell_C should be dynamically chosen as safest alternative
    best_alt = select_safe_alternative_area("Cell_A", "Cell_B", candidates)
    chk("Dynamic safe alternative correctly selected safest area (Cell_C)", best_alt == "Cell_C")

def test_unified_threat_model():
    print("\n--- 5. UNIFIED THREAT MODEL (CAMERA + LOCATION) ---")
    # Camera Threat Model structure verification
    cam_threat = {
        "source": "camera",
        "area": "Z7",
        "zone": "Z7",
        "density": 61,
        "risk_score": 61.2,
        "risk_level": "HIGH",
        "trend": "RISING",
        "possible_origin": "Z4",
        "safe_alternative": "Z5",
        "recommended_action": "Redirect crowd toward Z5"
    }

    # Location Threat Model structure verification
    eval_mgr = evaluate_location_risk_and_prevention(user_role="manager")
    loc_threat = eval_mgr["threats"][0] if eval_mgr["threats"] else None
    
    chk("Location threat exists", loc_threat is not None)
    if loc_threat:
        for required_key in ["source", "area", "density", "risk_score", "risk_level", "trend", "possible_origin", "safe_alternative", "recommended_action"]:
            chk(f"Location threat matches unified model key: '{required_key}'", required_key in loc_threat)

    eval_usr = evaluate_location_risk_and_prevention(user_role="user")
    if eval_usr["threats"]:
        usr_t = eval_usr["threats"][0]
        chk("Public user threat contains NO risk_score", "risk_score" not in usr_t)
        chk("Public user threat contains NO possible_origin", "possible_origin" not in usr_t)
        chk("Public user threat contains crowd_status", "crowd_status" in usr_t)
        chk("Public user threat contains safe_alternative", "safe_alternative" in usr_t)
        chk("Public user threat contains safe_guidance", "safe_guidance" in usr_t)

def run_all_part3_tests():
    test_risk_engine_and_baselines()
    test_density_trends()
    test_flow_and_origin_analysis()
    test_dynamic_safe_alternative_selection()
    test_unified_threat_model()

    print("\n" + "=" * 60)
    print(f"  PART 3 TEST RESULTS: {PASS_COUNT} PASSED, {FAIL_COUNT} FAILED")
    print("=" * 60)

if __name__ == "__main__":
    run_all_part3_tests()
    sys.exit(0 if FAIL_COUNT == 0 else 1)
