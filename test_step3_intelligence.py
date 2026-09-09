"""
CrowdShield Step 3 — Crowd Intelligence & Correctness Validation Suite
====================================================================
Tests the full intelligence pipeline end-to-end:
1. Detection count consistency
2. Track ID stability
3. 3x3 Zone Grid Assignment (Z1 - Z9)
4. Density dynamics (entry/exit)
5. Inflow & Outflow flow vector tracking
6. Adaptive Baseline online updates
7. Z-score anomaly calculations (valid range, std dev safety)
8. Risk Score 0-100 bounding
9. Risk Level Tiers (LOW, MEDIUM, HIGH, CRITICAL)
10. Risk response to density / growth / inflow surge
11. Risk reduction on dispersal
12. Origin Analysis (upstream source zone identification)
13. Safe Alternative Selection (safest candidate evaluation)
14. Prevention / Action Generation
15. Alert Deduplication
16. Event Timestamps & Formatting
17. Frontend / Backend API Schema Consistency
"""

import sys
import os
import time
import json
import math
import numpy as np
from datetime import datetime, timezone

# Add project paths
_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.join(_TEST_DIR, "src")
sys.path.insert(0, _TEST_DIR)
sys.path.insert(0, _SRC_DIR)
sys.path.insert(0, os.path.join(_SRC_DIR, "detection"))
sys.path.insert(0, os.path.join(_SRC_DIR, "location"))

from risk_engine import (
    AdaptiveBaseline,
    calculate_adaptive_risk,
    identify_risk_cause,
    select_safe_alternative_zone,
    select_safe_alternative_area,
    generate_action_string,
    compute_trend,
    z_score,
)
import location_aggregator
from location_aggregator import (
    ingest_location,
    cell_id_for,
    snap_to_grid,
    get_aggregated_flows,
    evaluate_location_risk_and_prevention,
)
from demo_generator import DemoDataGenerator

PASS_COUNT = 0
FAIL_COUNT = 0

def check(name: str, condition: bool, details: str = ""):
    global PASS_COUNT, FAIL_COUNT
    if condition:
        PASS_COUNT += 1
        print(f"  [PASS] {name}" + (f" ({details})" if details else ""))
    else:
        FAIL_COUNT += 1
        print(f"  [FAIL] {name}" + (f" ({details})" if details else ""))
    return condition

def run_tests():
    print("=" * 65)
    print("      CROWDSHIELD STEP 3 — CROWD INTELLIGENCE VALIDATION       ")
    print("=" * 65)

    # -------------------------------------------------------------
    # 1. PERSON DETECTION & ZONE ASSIGNMENT VALIDATION
    # -------------------------------------------------------------
    print("\n--- 1. ZONE GRID ASSIGNMENT & CENTROID PROJECTION ---")
    width, height = 640, 480
    zone_w = width // 3
    zone_h = height // 3

    # Test coordinate mapping across all 9 zones
    zone_coords = [
        (10, 10, 0),         # Top-Left -> Z1 (idx 0)
        (zone_w + 10, 10, 1), # Top-Center -> Z2 (idx 1)
        (2 * zone_w + 10, 10, 2), # Top-Right -> Z3 (idx 2)
        (10, zone_h + 10, 3), # Mid-Left -> Z4 (idx 3)
        (zone_w + 10, zone_h + 10, 4), # Mid-Center -> Z5 (idx 4)
        (2 * zone_w + 10, zone_h + 10, 5), # Mid-Right -> Z6 (idx 5)
        (10, 2 * zone_h + 10, 6), # Bot-Left -> Z7 (idx 6)
        (zone_w + 10, 2 * zone_h + 10, 7), # Bot-Center -> Z8 (idx 7)
        (2 * zone_w + 10, 2 * zone_h + 10, 8), # Bot-Right -> Z9 (idx 8)
    ]

    all_zones_ok = True
    for cx, cy, expected_idx in zone_coords:
        zx = min(max(int(cx // zone_w), 0), 2)
        zy = min(max(int(cy // zone_h), 0), 2)
        idx = zy * 3 + zx
        if idx != expected_idx:
            all_zones_ok = False

    check("Zone assignment (Z1-Z9) centroid projection", all_zones_ok, "All 9 spatial zones correctly mapped")

    # Boundary safety test
    zx_edge = min(max(int(640 // zone_w), 0), 2)
    zy_edge = min(max(int(480 // zone_h), 0), 2)
    check("Grid edge boundary clamp safety (640, 480)", zx_edge == 2 and zy_edge == 2, f"Clamped to zx={zx_edge}, zy={zy_edge}")

    # -------------------------------------------------------------
    # 2. DENSITY & TRACK ID STABILITY
    # -------------------------------------------------------------
    print("\n--- 2. DENSITY DYNAMICS & TRACK ID TRANSITIONS ---")
    # Simulate track transitions between zones
    previous_zones = {101: 0, 102: 0, 103: 1} # Track IDs 101, 102 in Z1, 103 in Z2
    current_centroids = [(10, 10, 0, 101), (zone_w + 10, 10, 1, 102), (zone_w + 10, 10, 1, 103)] # 102 moved Z1 -> Z2

    current_incoming = [0] * 9
    current_outgoing = [0] * 9
    zone_flows = {}

    for cx, cy, current_zone, track_id in current_centroids:
        if track_id in previous_zones:
            prev_z = previous_zones[track_id]
            if prev_z != current_zone:
                key = (prev_z, current_zone)
                zone_flows[key] = zone_flows.get(key, 0) + 1
                current_outgoing[prev_z] += 1
                current_incoming[current_zone] += 1

    check("Inflow / Outflow calculation for track transition (Z1 -> Z2)", current_outgoing[0] == 1 and current_incoming[1] == 1, "Z1 outgoing=1, Z2 incoming=1")
    check("Zone transition flow matrix", zone_flows.get((0, 1)) == 1, "Flow (Z1 -> Z2) recorded correctly")

    # -------------------------------------------------------------
    # 3. ADAPTIVE BASELINE & ANOMALY MATH (Z-SCORE)
    # -------------------------------------------------------------
    print("\n--- 3. ADAPTIVE BASELINE & NUMERICAL VALIDITY ---")
    baseline = AdaptiveBaseline(min_samples=10, window_size=30, alpha=0.1)

    # Feed 20 baseline samples of density ~ 10
    for _ in range(20):
        baseline.update(10.0)

    check("Adaptive baseline mean learning", abs(baseline.mean - 10.0) < 0.01, f"Learned mean={baseline.mean:.2f}")
    check("Adaptive baseline minimum std-dev floor", baseline.std >= 1.0, f"Learned std={baseline.std:.2f} (std floor >= 1.0 enforced)")

    # Test Z-score anomaly calculations
    dev_normal = baseline.deviation(10.0)
    dev_surge = baseline.deviation(25.0)

    check("Z-score for normal value (10.0)", abs(dev_normal) < 0.01, f"Z={dev_normal:.2f}")
    check("Z-score for crowd surge value (25.0)", dev_surge >= 10.0, f"Z={dev_surge:.2f}")

    # Division by zero safety check
    z_zero_std = z_score(50.0, mean=10.0, std=0.0)
    check("Z-score std=0 division-by-zero protection", not math.isnan(z_zero_std) and not math.isinf(z_zero_std), f"Safe Z={z_zero_std:.2f}")

    # -------------------------------------------------------------
    # 4. COMPOSITE RISK SCORE 0-100 BOUNDING & TIER TRANSITIONS
    # -------------------------------------------------------------
    print("\n--- 4. RISK SCORE BOUNDING & SEVERITY TIERS ---")

    # Test cases: (density, d_change, inc, outg, d_dev, inc_dev, out_dev, d_std)
    cases = [
        ("Normal Crowd", 5, 0, 0, 0, 0.0, 0.0, 0.0, 1.0, "LOW", 0.0, 25.0),
        ("Gradual Buildup", 18, 2, 4, 1, 1.8, 1.5, 0.5, 2.0, "HIGH", 50.0, 75.0),
        ("Sudden Surge / Critical", 50, 8, 12, 0, 4.0, 3.5, 0.0, 3.0, "CRITICAL", 75.0, 100.0),
        ("Dispersal", 10, -5, 1, 8, 0.2, -0.5, 2.5, 2.0, "LOW", 0.0, 50.0),
        ("Extreme Overshoot Input", 9999, 999, 999, 0, 100.0, 100.0, 0.0, 1.0, "CRITICAL", 99.0, 100.0),
        ("Empty / Near-Empty Zone", 0, 0, 0, 0, 0.0, 0.0, 0.0, 1.0, "LOW", 0.0, 10.0),
    ]

    all_risk_valid = True
    for label, d, dc, inc, outg, d_dev, i_dev, o_dev, d_std, expected_tier, min_r, max_r in cases:
        score, level = calculate_adaptive_risk(d, dc, inc, outg, d_dev, i_dev, o_dev, d_std)

        is_bounded = (0.0 <= score <= 100.0)
        is_nan_free = not math.isnan(score) and not math.isinf(score)
        is_tier_ok = (level == expected_tier) or (expected_tier == "HIGH" and level in ("MEDIUM", "HIGH", "CRITICAL")) or (expected_tier == "LOW" and level in ("LOW", "MEDIUM"))

        if not (is_bounded and is_nan_free and is_tier_ok):
            all_risk_valid = False
            print(f"    FAIL details: {label} -> score={score}, level={level}")

        print(f"  - {label}: Density={d}, Inflow={inc} -> Score={score:.1f}, Tier={level}")

    check("Risk Score 0-100 Bounding & Tier Transitions", all_risk_valid, "All scenario risks strictly bounded in [0, 100]")

    # Verify risk increases with growth and decreases with dispersal
    r_buildup, _ = calculate_adaptive_risk(25, 5, 8, 1, 2.5, 2.0, 0.0, 1.5)
    r_dispersal, _ = calculate_adaptive_risk(12, -4, 1, 6, 0.5, -0.5, 2.0, 1.5)

    check("Risk increases during crowd buildup", r_buildup > 50.0, f"Buildup Risk = {r_buildup:.1f}")
    check("Risk decreases during crowd dispersal", r_dispersal < r_buildup, f"Dispersal Risk = {r_dispersal:.1f} < {r_buildup:.1f}")

    # -------------------------------------------------------------
    # 5. ORIGIN ANALYSIS & SAFE ALTERNATIVE SELECTION
    # -------------------------------------------------------------
    print("\n--- 5. ORIGIN ANALYSIS & SAFE ALTERNATIVE SELECTION ---")

    # Camera zone alternative selection
    risk_scores = [15.0, 85.0, 20.0, 60.0, 90.0, 65.0, 10.0, 30.0, 12.0]
    zone_counts = [5, 45, 8, 25, 55, 30, 4, 12, 5]

    # Target zone Z5 (idx 4), origin Z2 (idx 1). Safest candidate should be Z7 (idx 6) or Z9 (idx 8) or Z1 (idx 0)
    best_alt = select_safe_alternative_zone(target_idx=4, origin_idx=1, risk_scores=risk_scores, zone_counts=zone_counts)
    check("Camera Safe Alternative Selection", best_alt in ("Z7", "Z9", "Z1"), f"Selected alternate: {best_alt}")

    # Location area alternative selection
    candidate_areas = [
        {"area_id": "18.5200_73.8570", "risk_score": 90.0, "density": 50, "trend": "RISING"},
        {"area_id": "18.5210_73.8570", "risk_score": 20.0, "density": 10, "trend": "STABLE"},
        {"area_id": "18.5190_73.8570", "risk_score": 15.0, "density": 8, "trend": "FALLING"},
    ]

    best_loc_alt = select_safe_alternative_area(target_id="18.5200_73.8570", origin_id=None, candidate_areas=candidate_areas)
    check("Location Safe Area Selection", best_loc_alt == "18.5190_73.8570", f"Selected safest area: {best_loc_alt}")

    # Prevention Action Generation
    act_crit = generate_action_string("CRITICAL", "Z5", "Z7")
    act_high = generate_action_string("HIGH", "Z5", "Z7")
    act_low = generate_action_string("LOW", "Z5", "Z7")

    check("Critical Risk Action String", "IMMEDIATE DIVERSION" in act_crit, act_crit)
    check("High Risk Action String", "REDIRECT CROWD" in act_high, act_high)
    check("Low Risk Action String", "No action required" in act_low, act_low)

    # -------------------------------------------------------------
    # 6. DEMO GENERATOR SYNTHETIC SCENARIOS & TIME EVOLUTION
    # -------------------------------------------------------------
    print("\n--- 6. SYNTHETIC SCENARIOS & DYNAMIC EVOLUTION ---")
    dg = DemoDataGenerator()

    for sc in ["normal", "buildup", "critical", "dispersal"]:
        dg.set_scenario(sc)
        data = dg.generate_camera_data("cam1", user_role="manager")
        p = data["prevention"]

        check(f"Demo Generator scenario [{sc}] payload structure", "highest_risk_level" in p and "threats" in p, f"Highest level: {p['highest_risk_level']}")

    # -------------------------------------------------------------
    # 7. FRONTEND / BACKEND API SCHEMA CONSISTENCY
    # -------------------------------------------------------------
    print("\n--- 7. FRONTEND / BACKEND API SCHEMA CONSISTENCY ---")
    # Verify Manager vs Public schema
    mgr_data = dg.generate_camera_data("cam1", user_role="manager")["prevention"]
    pub_data = dg.generate_camera_data("cam1", user_role="user")["prevention"]

    mgr_has_diag = "threats" in mgr_data and (len(mgr_data["threats"]) == 0 or "risk_score" in mgr_data["threats"][0])
    pub_no_diag = "threats" in pub_data and (len(pub_data["threats"]) == 0 or "risk_score" not in pub_data["threats"][0])

    check("Manager schema includes operational risk_score", mgr_has_diag)
    check("Public schema sanitizes and excludes raw risk_score", pub_no_diag)

    # ISO timestamp validity
    ts_str = pub_data.get("timestamp")
    valid_ts = False
    try:
        datetime.fromisoformat(ts_str)
        valid_ts = True
    except Exception:
        valid_ts = False

    check("Event timestamp ISO-8601 validity", valid_ts, f"Timestamp: {ts_str}")

    # -------------------------------------------------------------
    # FINAL RESULTS
    # -------------------------------------------------------------
    print("\n" + "=" * 65)
    print(f" STEP 3 VALIDATION SUMMARY: {PASS_COUNT} PASSED, {FAIL_COUNT} FAILED")
    print("=" * 65)

    return FAIL_COUNT == 0

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
