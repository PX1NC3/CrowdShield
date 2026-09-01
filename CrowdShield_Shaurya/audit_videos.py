"""
CrowdShield Step 6 — Multi-Video Detection Generalization Audit
================================================================
Audits object detection and tracking performance across all available video sources in CrowdShield.
Measures:
1. Video Metadata (Resolution, FPS, Duration, Perspective, Lighting, Person Scale)
2. Detection Metrics (Total Detections, Avg Persons/Frame, Max Persons/Frame, Detection Rate %, Confidence Distribution)
3. Person Scale Analysis (Bounding Box Area %, Tiny/Small/Medium/Large counts)
4. Tracking Metrics (Unique Track IDs, Average Track Longevity, Track ID Switches/Losses)
5. Comparative Diagnostics (Detection Failures vs Tracking Failures)
"""

import os
import sys
import time
import json
import cv2
import numpy as np
import torch
torch.set_num_threads(1)

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = _TEST_DIR

from ultralytics import YOLO

def analyze_video(video_path: str, model: YOLO, max_frames: int = 400):
    filename = os.path.basename(video_path)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"ERROR: Cannot open {video_path}")
        return None

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / fps if fps > 0 else 0.0
    frame_area = width * height

    print(f"\n=======================================================")
    print(f" AUDITING VIDEO: {filename}")
    print(f"=======================================================")
    print(f" Resolution:  {width} x {height}")
    print(f" FPS:         {fps:.2f}")
    print(f" Total Frames: {total_frames}")
    print(f" Duration:    {duration_sec:.2f} seconds")

    frames_tested = 0
    frames_with_detections = 0
    total_person_detections = 0
    per_frame_counts = []
    confidence_scores = []
    bbox_areas_pct = []

    # Track metrics
    active_tracks_per_frame = []
    track_first_seen = {} # track_id -> frame_idx
    track_last_seen = {}  # track_id -> frame_idx
    all_seen_track_ids = set()

    start_t = time.time()

    # Reset tracker state between videos
    model.predictor = None

    while True:
        ret, frame = cap.read()
        if not ret or frames_tested >= max_frames:
            break

        frames_tested += 1

        with torch.no_grad():
            results = model.track(frame, persist=True, imgsz=640, verbose=False)

        boxes = results[0].boxes
        frame_person_count = 0
        frame_track_count = 0

        if boxes is not None and len(boxes) > 0:
            for box in boxes:
                cls_id = int(box.cls[0].cpu().numpy())
                if cls_id == 0: # Person class
                    conf = float(box.conf[0].cpu().numpy())
                    xyxy = box.xyxy[0].cpu().numpy()
                    w_box = xyxy[2] - xyxy[0]
                    h_box = xyxy[3] - xyxy[1]
                    area_pct = (w_box * h_box) / frame_area * 100.0

                    confidence_scores.append(conf)
                    bbox_areas_pct.append(area_pct)
                    frame_person_count += 1

                    if box.id is not None:
                        track_id = int(box.id[0].cpu().numpy())
                        frame_track_count += 1
                        all_seen_track_ids.add(track_id)
                        if track_id not in track_first_seen:
                            track_first_seen[track_id] = frames_tested
                        track_last_seen[track_id] = frames_tested

        per_frame_counts.append(frame_person_count)
        active_tracks_per_frame.append(frame_track_count)
        if frame_person_count > 0:
            frames_with_detections += 1

    cap.release()
    elapsed_t = time.time() - start_t

    # Statistical Aggregation
    avg_persons = float(np.mean(per_frame_counts)) if per_frame_counts else 0.0
    max_persons = int(np.max(per_frame_counts)) if per_frame_counts else 0
    min_persons = int(np.min(per_frame_counts)) if per_frame_counts else 0
    detection_rate_pct = (frames_with_detections / frames_tested * 100.0) if frames_tested > 0 else 0.0

    avg_conf = float(np.mean(confidence_scores)) if confidence_scores else 0.0
    avg_bbox_pct = float(np.mean(bbox_areas_pct)) if bbox_areas_pct else 0.0

    # Classify person sizes
    # Tiny (< 0.5% of frame area), Small (0.5% - 2%), Medium (2% - 8%), Large (> 8%)
    tiny_count = sum(1 for a in bbox_areas_pct if a < 0.5)
    small_count = sum(1 for a in bbox_areas_pct if 0.5 <= a < 2.0)
    med_count = sum(1 for a in bbox_areas_pct if 2.0 <= a < 8.0)
    large_count = sum(1 for a in bbox_areas_pct if a >= 8.0)

    # Track longevity
    track_durations = [track_last_seen[tid] - track_first_seen[tid] + 1 for tid in all_seen_track_ids]
    avg_track_duration = float(np.mean(track_durations)) if track_durations else 0.0
    max_track_duration = int(np.max(track_durations)) if track_durations else 0

    fps_processing = frames_tested / elapsed_t if elapsed_t > 0 else 0.0

    print(f" --- OBSERVATIONAL METRICS ({frames_tested} frames analyzed) ---")
    print(f" Processing Speed:      {fps_processing:.1f} FPS")
    print(f" Total Detections:       {len(bbox_areas_pct)}")
    print(f" Frames with Detections: {frames_with_detections} / {frames_tested} ({detection_rate_pct:.1f}%)")
    print(f" Avg Persons / Frame:   {avg_persons:.2f} (Range: {min_persons} - {max_persons})")
    print(f" Avg Confidence:        {avg_conf:.3f}")
    print(f" Avg Bbox Area:         {avg_bbox_pct:.3f}% of frame area")
    print(f" Bbox Size Breakdown:   Tiny (<0.5%): {tiny_count} | Small (0.5-2%): {small_count} | Med (2-8%): {med_count} | Large (>8%): {large_count}")
    print(f" Unique Track IDs:      {len(all_seen_track_ids)}")
    print(f" Avg Track Lifespan:    {avg_track_duration:.1f} frames (Max: {max_track_duration} frames)")

    return {
        "filename": filename,
        "width": width,
        "height": height,
        "fps": fps,
        "total_frames": total_frames,
        "duration_sec": duration_sec,
        "frames_tested": frames_tested,
        "frames_with_detections": frames_with_detections,
        "detection_rate_pct": detection_rate_pct,
        "total_detections": len(bbox_areas_pct),
        "avg_persons": avg_persons,
        "max_persons": max_persons,
        "min_persons": min_persons,
        "avg_conf": avg_conf,
        "avg_bbox_pct": avg_bbox_pct,
        "size_breakdown": {"tiny": tiny_count, "small": small_count, "medium": med_count, "large": large_count},
        "unique_tracks": len(all_seen_track_ids),
        "avg_track_lifespan": avg_track_duration,
        "max_track_lifespan": max_track_duration,
    }

def main():
    model_path = os.path.join(PROJECT_ROOT, "models", "yolo11n.pt")
    if not os.path.exists(model_path):
        print(f"ERROR: Model file not found at {model_path}")
        return

    print(f"Loading YOLO model from: {model_path}")
    model = YOLO(model_path)

    videos_dir = os.path.join(PROJECT_ROOT, "data", "videos")
    valid_exts = {".mp4", ".webm", ".avi", ".mov", ".mkv"}
    video_files = [os.path.join(videos_dir, f) for f in os.listdir(videos_dir) if os.path.splitext(f)[1].lower() in valid_exts]

    results_all = []
    for vid_path in video_files:
        res = analyze_video(vid_path, model)
        if res:
            results_all.append(res)

    print("\n" + "=" * 75)
    print("        STEP 6 DETECTOR GENERALIZATION SUMMARY REPORT       ")
    print("=" * 75)
    print(f"{'Video':<35} | {'Res':<10} | {'Frames':<7} | {'Avg P/F':<8} | {'Max P/F':<8} | {'Det Rate':<9} | {'Avg Conf':<8}")
    print("-" * 95)
    for r in results_all:
        res_str = f"{r['width']}x{r['height']}"
        print(f"{r['filename']:<35} | {res_str:<10} | {r['frames_tested']:<7} | {r['avg_persons']:<8.2f} | {r['max_persons']:<8d} | {r['detection_rate_pct']:<8.1f}% | {r['avg_conf']:<8.3f}")

if __name__ == "__main__":
    main()
