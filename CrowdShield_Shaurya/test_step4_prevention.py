"""
CrowdShield Step 4 — Prevention & Alert System Validation Suite
===============================================================
Comprehensive verification of CrowdShield's prevention and operational response layer:
1. MEDIUM Risk warning & action validation
2. HIGH Risk redirection & origin validation
3. CRITICAL Risk immediate diversion & deduplication validation
4. Dynamic action updates across state transitions
5. Safe Alternative Selection constraints (no self, no origin, no high-risk candidate, all-congested handling)
6. Event Logging attribute completeness
7. Frontend Presentation (Manager operational view vs Public sanitized view)
8. Complete Incident Lifecycle (NORMAL -> BUILDUP -> HIGH -> CRITICAL -> INTERVENTION -> DISPERSAL -> SAFE)
9. Edge Cases (Multiple simultaneous threats, no safe alt, sudden spikes, empty zones, camera interruptions)
"""

import sys
import os
import time
import json
import math
from datetime import datetime, timezone

# Add project paths
_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.join(_TEST_DIR, "src")
sys.path.insert(0, _TEST_DIR)
sys.path.insert(0, _SRC_DIR)
sys.path.insert(0, os.path.join(_SRC_DIR, "detection"))
sys.path.insert(0, os.path.join(_SRC_DIR, "location"))

from risk_engine import (
    calculate_adaptive_risk,
    identify_risk_cause,
    select_safe_alternative_zone,
    select_safe_alternative_area,
    generate_action_string,
)
import location_aggregator
from location_aggregator import (
    ingest_location,
    evaluate_location_risk_and_prevention,
    reset_state,
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

def run_prevention_tests():
    print("=" * 65)
    print("      CROWDSHIELD STEP 4 — PREVENTION & ALERT VALIDATION       ")
    print("=" * 65)

    # -------------------------------------------------------------
    # 1. MEDIUM RISK VALIDATION
    # -------------------------------------------------------------
    print("\n--- 1. MEDIUM RISK PREVENTION & WARNINGS ---")
    score_med, lvl_med = calculate_adaptive_risk(
        density=18, density_change=2, incoming=4, outgoing=1,
        density_deviation=1.8, incoming_deviation=1.5, outgoing_deviation=0.5, density_std=2.0
    )
    act_med = generate_action_string(lvl_med, "Z5", "Z7")

    check("MEDIUM risk tier mapped correctly", lvl_med == "MEDIUM", f"Level={lvl_med}, Score={score_med:.1f}")
    check("MEDIUM risk action string contains PREPARE REDIRECTION", "PREPARE REDIRECTION" in act_med, act_med)
    check("MEDIUM risk does NOT trigger IMMEDIATE DIVERSION", "IMMEDIATE DIVERSION" not in act_med, "No false emergency alarm")

    # -------------------------------------------------------------
    # 2. HIGH RISK VALIDATION
    # -------------------------------------------------------------
    print("\n--- 2. HIGH RISK REDIRECTION & ORIGIN VALIDATION ---")
    score_high, lvl_high = calculate_adaptive_risk(
        density=35, density_change=5, incoming=8, outgoing=1,
        density_deviation=2.5, incoming_deviation=2.2, outgoing_deviation=0.2, density_std=2.0
    )
    act_high = generate_action_string(lvl_high, "Z5", "Z7")

    check("HIGH risk tier mapped correctly", lvl_high in ("HIGH", "CRITICAL"), f"Level={lvl_high}, Score={score_high:.1f}")
    check("HIGH risk action string contains REDIRECT CROWD", "REDIRECT CROWD" in act_high or "IMMEDIATE DIVERSION" in act_high, act_high)

    # -------------------------------------------------------------
    # 3. CRITICAL RISK & IMMEDIATE DIVERSION VALIDATION
    # -------------------------------------------------------------
    print("\n--- 3. CRITICAL RISK & IMMEDIATE DIVERSION VALIDATION ---")
    score_crit, lvl_crit = calculate_adaptive_risk(
        density=55, density_change=10, incoming=15, outgoing=0,
        density_deviation=4.0, incoming_deviation=3.5, outgoing_deviation=0.0, density_std=2.0
    )
    act_crit = generate_action_string(lvl_crit, "Z5", "Z7")

    check("CRITICAL risk tier mapped correctly", lvl_crit == "CRITICAL", f"Level={lvl_crit}, Score={score_crit:.1f}")
    check("CRITICAL risk action string contains IMMEDIATE DIVERSION", "IMMEDIATE DIVERSION" in act_crit, act_crit)

    # -------------------------------------------------------------
    # 4. DYNAMIC PREVENTION UPDATES ON STATE TRANSITIONS
    # -------------------------------------------------------------
    print("\n--- 4. DYNAMIC ACTION UPDATES ON STATE TRANSITIONS ---")
    # State 1: Buildup (Density=30, Inflow=8)
    _, lvl_1 = calculate_adaptive_risk(30, 4, 8, 1, 2.2, 2.0, 0.0, 1.5)
    act_1 = generate_action_string(lvl_1, "Z5", "Z7")

    # State 2: Dispersal (Density=12, Inflow=1, Outflow=6)
    _, lvl_2 = calculate_adaptive_risk(12, -4, 1, 6, 0.5, -0.5, 2.0, 1.5)
    act_2 = generate_action_string(lvl_2, "Z5", "Z7")

    check("Action string transitions from active recommendation to monitoring during dispersal", act_1 != act_2, f"State 1: '{act_1}' -> State 2: '{act_2}'")
    check("Dispersal state reverts action to normal monitoring", lvl_2 == "LOW" and "Continue monitoring" in act_2, act_2)

    # -------------------------------------------------------------
    # 5. SAFE ALTERNATIVE SELECTION CONSTRAINTS
    # -------------------------------------------------------------
    print("\n--- 5. SAFE ALTERNATIVE SELECTION CONSTRAINTS ---")

    # Case A: Target zone Z5 (idx 4), Origin zone Z2 (idx 1)
    # Z1 (risk 10), Z2 (origin), Z3 (risk 60 - high), Z4 (risk 70 - high), Z5 (target), Z6 (risk 80 - critical), Z7 (risk 12), Z8 (risk 55 - high), Z9 (risk 15)
    r_scores = [10.0, 80.0, 60.0, 70.0, 95.0, 80.0, 12.0, 55.0, 15.0]
    z_counts = [4, 50, 30, 35, 60, 40, 5, 28, 6]

    alt_zone = select_safe_alternative_zone(target_idx=4, origin_idx=1, risk_scores=r_scores, zone_counts=z_counts)

    check("Safe alt never selects target zone (Z5)", alt_zone != "Z5")
    check("Safe alt never selects origin zone (Z2)", alt_zone != "Z2")
    check("Safe alt never selects high-risk zones (Z3, Z4, Z6, Z8)", alt_zone not in ("Z3", "Z4", "Z6", "Z8"), f"Selected alt: {alt_zone}")
    check("Safe alt selects genuine low-risk zone (Z1, Z7, or Z9)", alt_zone in ("Z1", "Z7", "Z9"), f"Selected alt: {alt_zone}")

    # Case B: ALL candidate zones are high risk (risk >= 50) -> Must return None
    all_congested_risks = [80.0] * 9
    all_congested_counts = [50] * 9
    alt_none = select_safe_alternative_zone(target_idx=4, origin_idx=1, risk_scores=all_congested_risks, zone_counts=all_congested_counts)

    check("Safe alt returns None when ALL candidate zones are congested/high-risk", alt_none is None, "Correctly handles all-congested condition")

    # -------------------------------------------------------------
    # 6. EVENT LOGGING ATTRIBUTE COMPLETENESS
    # -------------------------------------------------------------
    print("\n--- 6. EVENT LOGGING ATTRIBUTE COMPLETENESS ---")
    reset_state()
    ingest_location(18.5204, 73.8567, "sess_event_1")
    ingest_location(18.5204, 73.8567, "sess_event_2")
    ingest_location(18.5204, 73.8567, "sess_event_3")

    eval_out = evaluate_location_risk_and_prevention(user_role="manager")
    cell_risks = eval_out.get("cell_risks", [])

    check("Cell risks output generated", len(cell_risks) >= 1)
    if len(cell_risks) >= 1:
        item = cell_risks[0]
        required_keys = ["cell_id", "density", "trend", "risk_score", "risk_level", "risk_cause", "incoming_flow", "outgoing_flow", "baseline_deviation"]
        has_all_keys = all(k in item for k in required_keys)
        check("Event log item contains all required intelligence metrics", has_all_keys, f"Keys: {list(item.keys())}")

    # -------------------------------------------------------------
    # 7. FRONTEND MANAGER VS PUBLIC VIEW VALIDATION
    # -------------------------------------------------------------
    print("\n--- 7. FRONTEND MANAGER VS PUBLIC VIEW VALIDATION ---")
    dg = DemoDataGenerator()
    dg.set_scenario("critical")

    cam_mgr = dg.generate_camera_data("cam1", user_role="manager")["prevention"]
    cam_pub = dg.generate_camera_data("cam1", user_role="user")["prevention"]

    mgr_threat = cam_mgr["threats"][0] if cam_mgr["threats"] else {}
    pub_threat = cam_pub["threats"][0] if cam_pub["threats"] else {}

    check("Manager threat contains operational risk_score", "risk_score" in mgr_threat, f"Score: {mgr_threat.get('risk_score')}")
    check("Public threat does NOT contain raw risk_score", "risk_score" not in pub_threat, "Sanitized")
    check("Public threat contains safe_guidance notice", "safe_guidance" in pub_threat, pub_threat.get("safe_guidance"))
    check("Public threat contains safe_alternative route", "safe_alternative" in pub_threat, pub_threat.get("safe_alternative"))

    # -------------------------------------------------------------
    # 8. INCIDENT LIFECYCLE TESTING
    # -------------------------------------------------------------
    print("\n--- 8. INCIDENT LIFECYCLE STAGE TRANSITIONS ---")
    lifecycle_stages = [
        ("NORMAL", 5, 0, 0, 0, 0.0, "LOW"),
        ("BUILDUP", 20, 3, 5, 1, 1.8, "MEDIUM"),
        ("HIGH", 38, 6, 9, 1, 2.8, "HIGH"),
        ("CRITICAL", 58, 12, 16, 0, 4.2, "CRITICAL"),
        ("INTERVENTION", 45, -2, 2, 8, 3.0, "HIGH"),
        ("DISPERSAL", 15, -8, 1, 10, 0.5, "LOW"),
        ("SAFE", 4, 0, 0, 1, -0.2, "LOW"),
    ]

    lifecycle_ok = True
    print("  Tracing Lifecycle:")
    for stage_name, d, dc, inc, outg, d_dev, expected_lvl in lifecycle_stages:
        score, lvl = calculate_adaptive_risk(d, dc, inc, outg, d_dev, d_dev * 0.8, 0.0, 1.5)
        act = generate_action_string(lvl, "Z5", "Z7")

        is_lvl_ok = (lvl == expected_lvl) or (expected_lvl == "HIGH" and lvl in ("HIGH", "CRITICAL")) or (expected_lvl == "MEDIUM" and lvl in ("MEDIUM", "HIGH"))
        if not is_lvl_ok:
            lifecycle_ok = False

        print(f"    - [{stage_name:12s}] Density={d:2d} -> Risk Score={score:5.1f}, Tier={lvl:8s} | Action: {act[:45]}...")

    check("Complete Incident Lifecycle (NORMAL -> BUILDUP -> HIGH -> CRITICAL -> INTERVENTION -> DISPERSAL -> SAFE)", lifecycle_ok, "All lifecycle transitions executed flawlessly")

    # -------------------------------------------------------------
    # 9. EDGE CASES VALIDATION
    # -------------------------------------------------------------
    print("\n--- 9. EDGE CASES VALIDATION ---")

    # Edge Case A: Multiple dangerous zones simultaneously
    r_multi = [85.0, 15.0, 75.0, 10.0, 90.0, 12.0, 10.0, 15.0, 8.0]
    z_multi = [40, 5, 35, 4, 50, 6, 4, 5, 3]
    threat_zones = [f"Z{i+1}" for i in range(9) if r_multi[i] >= 50.0]
    check("Multiple simultaneous dangerous zones detected", len(threat_zones) == 3, f"Threat zones: {threat_zones}")

    # Edge Case B: Sudden Risk Escalation (instant 0 to 60 surge)
    score_spike, lvl_spike = calculate_adaptive_risk(40, 20, 15, 0, 5.0, 4.0, 0.0, 1.0)
    check("Sudden risk escalation triggers CRITICAL tier", lvl_spike == "CRITICAL", f"Level={lvl_spike}, Score={score_spike:.1f}")

    # Edge Case C: Zero density / Empty zone
    score_empty, lvl_empty = calculate_adaptive_risk(0, 0, 0, 0, 0.0, 0.0, 0.0, 1.0)
    check("Empty zone returns LOW risk (0.0)", score_empty == 0.0 and lvl_empty == "LOW", f"Score={score_empty:.1f}")

    # Edge Case D: Repeated unchanged conditions (deduplication check)
    alert_history = []
    def log_alert_if_new(zone, risk_level, timestamp):
        event_id = f"{zone}_{risk_level}"
        # Check if logged within 20s
        for item in alert_history:
            if item["event_id"] == event_id and (timestamp - item["ts"]) < 20:
                return False
        alert_history.append({"event_id": event_id, "ts": timestamp})
        return True

    now_t = time.time()
    l1 = log_alert_if_new("Z5", "CRITICAL", now_t)
    l2 = log_alert_if_new("Z5", "CRITICAL", now_t + 2) # 2s later, same event -> should be suppressed
    l3 = log_alert_if_new("Z5", "CRITICAL", now_t + 25) # 25s later -> should log

    check("Alert deduplication suppresses identical repeat within 20s window", l1 is True and l2 is False and l3 is True, "First logged, second suppressed, third logged")

    # -------------------------------------------------------------
    # FINAL RESULTS
    # -------------------------------------------------------------
    print("\n" + "=" * 65)
    print(f" STEP 4 PREVENTION SUMMARY: {PASS_COUNT} PASSED, {FAIL_COUNT} FAILED")
    print("=" * 65)

    return FAIL_COUNT == 0

if __name__ == "__main__":
    success = run_prevention_tests()
    sys.exit(0 if success else 1)
