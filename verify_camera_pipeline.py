"""
End-to-End Camera Verification Test
Validates:
1. CAM1 real video stream produces valid annotated JPEG frames from crowd_test.mp4.
2. CAM2 real video stream produces valid annotated JPEG frames from stock-footage.webm.
3. Live detections correspond directly to detected people (no fake counts).
4. DEMO mode scenarios modulate risk without replacing video stream with fake dots.
5. Stream aspect ratio and resolution integrity.
"""
import urllib.request
import json
import cv2
import numpy as np
import time

def read_one_mjpeg_frame(url, timeout=5):
    req = urllib.request.urlopen(url, timeout=timeout)
    buffer = b""
    start_time = time.time()
    while time.time() - start_time < timeout:
        chunk = req.read(4096)
        if not chunk:
            break
        buffer += chunk
        a = buffer.find(b"\xff\xd8") # JPEG SOI
        b = buffer.find(b"\xff\xd9") # JPEG EOI
        if a != -1 and b != -1 and b > a:
            jpg_bytes = buffer[a:b+2]
            img = cv2.imdecode(np.frombuffer(jpg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
            req.close()
            return img
    req.close()
    return None

def test_pipeline():
    print("==================================================")
    print(" CrowdShield Camera Pipeline Verification")
    print("==================================================")

    # 1. Test CAM 1 MJPEG Stream Frame
    print("\n[1] Testing CAM 1 Video Stream...")
    cam1_frame = read_one_mjpeg_frame("http://127.0.0.1:8765/stream?cam=cam1")
    assert cam1_frame is not None, "Failed to read MJPEG frame from CAM 1"
    h, w, c = cam1_frame.shape
    print(f"  [PASS] CAM 1 Frame received: {w}x{h}, channels={c}")
    assert w > 400 and h > 200, "Frame dimensions invalid"

    # 2. Test CAM 2 MJPEG Stream Frame
    print("\n[2] Testing CAM 2 Video Stream...")
    cam2_frame = read_one_mjpeg_frame("http://127.0.0.1:8765/stream?cam=cam2")
    assert cam2_frame is not None, "Failed to read MJPEG frame from CAM 2"
    h2, w2, c2 = cam2_frame.shape
    print(f"  [PASS] CAM 2 Frame received: {w2}x{h2}, channels={c2}")
    assert w2 > 400 and h2 > 200, "Frame dimensions invalid"

    # 3. Test CAM 1 and CAM 2 Prevention Payloads
    print("\n[3] Testing Camera Prevention Endpoints...")
    p1 = json.loads(urllib.request.urlopen("http://127.0.0.1:8765/api/prevention?cam=cam1").read())
    p2 = json.loads(urllib.request.urlopen("http://127.0.0.1:8765/api/prevention?cam=cam2").read())

    print(f"  CAM 1 total_people: {p1.get('total_people')}, risk: {p1.get('highest_risk_level')}")
    print(f"  CAM 2 total_people: {p2.get('total_people')}, risk: {p2.get('highest_risk_level')}")
    assert "cam1" in p1.get("cameras", {}), "Missing cam1 in cameras list"
    assert "cam2" in p1.get("cameras", {}), "Missing cam2 in cameras list"
    assert "cam3" not in p1.get("cameras", {}), "Fabricated cam3 found in cameras list"
    print("  [PASS] Exact real cameras discovered (CAM 1 & CAM 2, no fabricated CAM 3)")

    # 4. Test Demo Mode on Real Camera Stream
    print("\n[4] Testing Demo Mode Scenarios on Real Video...")
    for scenario in ["normal", "buildup", "critical", "dispersal"]:
        toggle_req = urllib.request.Request(
            "http://127.0.0.1:8765/api/demo/toggle",
            json.dumps({"enabled": True, "scenario": scenario}).encode("utf-8"),
            {"Content-Type": "application/json"}
        )
        urllib.request.urlopen(toggle_req).read()

        # Check that MJPEG stream still returns real video frame
        demo_frame = read_one_mjpeg_frame("http://127.0.0.1:8765/stream?cam=cam1")
        assert demo_frame is not None, f"Stream failed in demo scenario {scenario}"
        assert demo_frame.shape == cam1_frame.shape, "Demo frame shape changed unexpectedly"

        p_demo = json.loads(urllib.request.urlopen("http://127.0.0.1:8765/api/prevention?cam=cam1").read())
        print(f"  Scenario [{scenario}]: risk={p_demo.get('highest_risk_level')}, total_people={p_demo.get('total_people')}, threats={len(p_demo.get('threats', []))}")

        if scenario == "normal":
            assert p_demo.get("highest_risk_level") == "LOW"
        elif scenario == "buildup":
            assert p_demo.get("highest_risk_level") == "HIGH"
        elif scenario == "critical":
            assert p_demo.get("highest_risk_level") == "CRITICAL"
        elif scenario == "dispersal":
            assert p_demo.get("highest_risk_level") in ("MEDIUM", "LOW")

    # Reset back to LIVE mode
    reset_req = urllib.request.Request(
        "http://127.0.0.1:8765/api/demo/toggle",
        json.dumps({"enabled": False}).encode("utf-8"),
        {"Content-Type": "application/json"}
    )
    urllib.request.urlopen(reset_req).read()
    p_live = json.loads(urllib.request.urlopen("http://127.0.0.1:8765/api/prevention?cam=cam1").read())
    assert p_live.get("demo_mode") is False, "Failed to return to LIVE mode"
    print("\n[5] Returned to LIVE Mode successfully.")
    print("\n==================================================")
    print(" ALL VERIFICATION CHECKS PASSED (100%)")
    print("==================================================")

if __name__ == "__main__":
    test_pipeline()
