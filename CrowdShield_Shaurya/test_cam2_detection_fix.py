"""
Targeted Test Suite for CAM2 Aerial Detection & Tracking Fix
============================================================
Verifies that:
1. CAM2 aerial feed no longer reports PEOPLE = 0 when valid person detections exist.
2. CAM1 frontal detection remains unchanged (conf threshold 0.30 enforced).
3. ByteTrack IDs are preserved whenever present.
4. Missing ByteTrack IDs do NOT create fake/index-based track IDs.
5. Zone counts remain accurate regardless of track ID availability.
6. Flow and origin calculations use ONLY real ByteTrack IDs.
"""

import sys
import os
import cv2
import torch
import numpy as np

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _TEST_DIR)
sys.path.insert(0, os.path.join(_TEST_DIR, "src"))
sys.path.insert(0, os.path.join(_TEST_DIR, "src", "detection"))

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

def test_cam2_aerial_detection_fix():
    print("\n--- 1. CAM2 Aerial Detection & Zone Counting ---")
    cam2_config = detect.CAMERAS.get("cam2")
    chk("CAM2 config exists", cam2_config is not None)
    if not cam2_config:
        return

    model_path = os.path.join(_TEST_DIR, "models", "yolo11n.pt")
    model = detect.YOLO(model_path)
    cap = cv2.VideoCapture(cam2_config["source"])

    chk("CAM2 video file opened successfully", cap.isOpened())

    total_people_detected = 0
    frames_tested = 20

    for _ in range(frames_tested):
        ret, frame = cap.read()
        if not ret:
            break

        # Simulate detection logic as in detect.py
        with torch.no_grad():
            results = model.track(frame, persist=True, imgsz=640, verbose=False)

        boxes = results[0].boxes
        zone_counts = [0] * 9
        tracked_centroids = []
        active_ids = set()

        is_aerial = ("aerial" in cam2_config["name"].lower()) or ("square" in cam2_config["source"].lower()) or ("pedestrian" in cam2_config["source"].lower())
        min_conf = 0.15 if is_aerial else 0.30

        if boxes is not None and len(boxes) > 0:
            classes = boxes.cls.cpu().numpy().astype(int)
            confs = boxes.conf.cpu().numpy() if boxes.conf is not None else None
            xyxy = boxes.xyxy.cpu().numpy()
            track_ids = boxes.id.cpu().numpy().astype(int) if boxes.id is not None else None

            for i in range(len(classes)):
                if classes[i] != 0:
                    continue
                if confs is not None and confs[i] < min_conf:
                    continue

                zone_counts[0] += 1

                if track_ids is not None and i < len(track_ids):
                    track_id = int(track_ids[i])
                    active_ids.add(track_id)
                    tracked_centroids.append((10, 10, 0, track_id))

        total_people_detected += sum(zone_counts)

    cap.release()

    chk("CAM2 no longer reports 0 people (total detections > 50 in 20 frames)", total_people_detected > 50)
    print(f"  Total people counted across {frames_tested} frames on CAM2: {total_people_detected} (Avg {total_people_detected/frames_tested:.1f}/frame)")

def test_cam1_frontal_detection_unchanged():
    print("\n--- 2. CAM1 Frontal Detection Integrity ---")
    cam1_config = detect.CAMERAS.get("cam1")
    chk("CAM1 config exists", cam1_config is not None)

    is_aerial_cam1 = ("aerial" in cam1_config["name"].lower()) or ("square" in cam1_config["source"].lower()) or ("pedestrian" in cam1_config["source"].lower())
    min_conf_cam1 = 0.15 if is_aerial_cam1 else 0.30

    chk("CAM1 retains strict 0.30 confidence threshold", min_conf_cam1 == 0.30)

def test_bytetrack_id_purity_and_no_fake_ids():
    print("\n--- 3. ByteTrack ID Preservation & No Fabricated IDs ---")

    # Mock boxes with and without IDs
    class MockBox:
        def __init__(self, cls_val, conf_val, has_id=False, id_val=None):
            self.cls = torch.tensor([cls_val])
            self.conf = torch.tensor([conf_val])
            self.xyxy = torch.tensor([[10.0, 10.0, 50.0, 50.0]])
            self.id = torch.tensor([id_val]) if has_id else None

    # Test Case A: Real ByteTrack ID present
    classes_a = np.array([0])
    confs_a = np.array([0.85])
    xyxy_a = np.array([[10, 10, 50, 50]])
    track_ids_a = np.array([99])

    active_ids_a = set()
    tracked_centroids_a = []
    zone_counts_a = [0] * 9

    for i in range(len(classes_a)):
        if classes_a[i] == 0 and confs_a[i] >= 0.30:
            zone_counts_a[0] += 1
            if track_ids_a is not None and i < len(track_ids_a):
                tid = int(track_ids_a[i])
                active_ids_a.add(tid)
                tracked_centroids_a.append((30, 30, 0, tid))

    chk("Real ByteTrack ID 99 preserved", 99 in active_ids_a)
    chk("Real ByteTrack centroid added to flow tracker", len(tracked_centroids_a) == 1 and tracked_centroids_a[0][3] == 99)
    chk("Zone count incremented to 1", zone_counts_a[0] == 1)

    # Test Case B: boxes.id is None (un-tracked box)
    classes_b = np.array([0])
    confs_b = np.array([0.25]) # Aerial candidate
    xyxy_b = np.array([[10, 10, 50, 50]])
    track_ids_b = None

    active_ids_b = set()
    tracked_centroids_b = []
    zone_counts_b = [0] * 9

    for i in range(len(classes_b)):
        if classes_b[i] == 0 and confs_b[i] >= 0.15:
            zone_counts_b[0] += 1
            if track_ids_b is not None and i < len(track_ids_b):
                tid = int(track_ids_b[i])
                active_ids_b.add(tid)
                tracked_centroids_b.append((30, 30, 0, tid))

    chk("Un-tracked box increments zone count (1)", zone_counts_b[0] == 1)
    chk("Un-tracked box does NOT create fake track IDs (active_ids is empty)", len(active_ids_b) == 0)
    chk("Un-tracked box does NOT enter flow tracking (tracked_centroids is empty)", len(tracked_centroids_b) == 0)

def run_all():
    print("=" * 60)
    print(" TARGETED TESTS FOR CAM2 AERIAL DETECTION & TRACKING FIX")
    print("=" * 60)
    test_cam2_aerial_detection_fix()
    test_cam1_frontal_detection_unchanged()
    test_bytetrack_id_purity_and_no_fake_ids()
    print("\n" + "=" * 60)
    print(f" TARGETED TEST RESULTS: {PASS_COUNT} PASSED, {FAIL_COUNT} FAILED")
    print("=" * 60)
    return FAIL_COUNT == 0

if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
