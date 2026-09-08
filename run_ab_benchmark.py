"""
CrowdShield Model A/B Benchmark: YOLOv8n vs person_best.pt
Evaluates both models on identical frames from CAM1 and CAM2 under matched inference conditions.
DOES NOT alter any production files.
"""

import os
import sys
import time
import json
import cv2
import numpy as np
from ultralytics import YOLO

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
BENCHMARK_DIR = os.path.join(PROJECT_ROOT, "benchmark")

# Model paths
MODEL_YOLOV8N = os.path.join(PROJECT_ROOT, "CrowdShield_Shaurya", "models", "yolov8n.pt")
MODEL_PERSON_BEST = os.path.join(PROJECT_ROOT, "CrowdShield_Shaurya", "models", "person_best.pt")

# Video paths
VIDEO_CAM1 = os.path.join(PROJECT_ROOT, "CrowdShield_Shaurya", "data", "videos", "crowd_test.mp4")
VIDEO_CAM2 = os.path.join(PROJECT_ROOT, "CrowdShield_Shaurya", "data", "videos", "stock-footage-busy-pedestrian-street-crowd-people-walking-on-around-city-square-view-from-the-top-aerial-shoot.webm")

# Inference parameters
IMGSZ = 960
CONF_THRESH = 0.25
CLASSES = [0]
FRAME_SAMPLE_COUNT = 80

CAM1_START_FRAME = 130  # Where active crowd appears
CAM2_START_FRAME = 20   # Active aerial crowd

def load_frames(video_path, start_frame, num_frames):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    frames = []
    frame_indices = []
    for i in range(num_frames):
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
        frame_indices.append(start_frame + i)
    cap.release()
    print(f"Loaded {len(frames)} frames from {os.path.basename(video_path)} (indices {frame_indices[0]} to {frame_indices[-1]})")
    return frames, frame_indices

def draw_annotations(frame, boxes, confs, track_ids, model_name, cam_name, frame_idx, avg_lat):
    annotated = frame.copy()
    h, w = annotated.shape[:2]
    
    # Header banner
    cv2.rectangle(annotated, (0, 0), (w, 48), (20, 20, 30), -1)
    title = f"{cam_name.upper()} | Model: {model_name} | Frame #{frame_idx} | Detections: {len(boxes)} | Latency: {avg_lat:.1f}ms"
    cv2.putText(annotated, title, (16, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 230, 255), 2, cv2.LINE_AA)
    
    # Draw boxes
    for i, box in enumerate(boxes):
        x1, y1, x2, y2 = [int(v) for v in box]
        conf = confs[i]
        tid = track_ids[i] if (track_ids is not None and len(track_ids) > i) else None
        
        color = (0, 255, 128) if "person_best" in model_name else (255, 165, 0)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        
        lbl = f"ID:{tid} {conf:.2f}" if tid is not None else f"{conf:.2f}"
        (tw, th), _ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        cv2.rectangle(annotated, (x1, max(0, y1 - th - 6)), (x1 + tw + 6, y1), color, -1)
        cv2.putText(annotated, lbl, (x1 + 3, max(th, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
        
    return annotated

def evaluate_model_on_frames(model_path, model_name, frames, frame_indices, save_annot_indices, out_img_dir, cam_name):
    os.makedirs(out_img_dir, exist_ok=True)
    # Warmup
    model = YOLO(model_path)
    dummy = np.zeros((480, 640, 3), dtype=np.uint8)
    _ = model.track(dummy, imgsz=IMGSZ, conf=CONF_THRESH, classes=CLASSES, persist=True, tracker="bytetrack.yaml", verbose=False)
    
    # Re-instantiate to reset tracker state cleanly
    del model
    model = YOLO(model_path)
    
    latencies = []
    detection_counts = []
    all_confs = []
    unique_ids = set()
    frames_zero_detections = 0
    per_frame_details = []
    
    for idx, (frame, f_num) in enumerate(zip(frames, frame_indices)):
        t0 = time.perf_counter()
        res = model.track(
            frame,
            imgsz=IMGSZ,
            conf=CONF_THRESH,
            classes=CLASSES,
            persist=True,
            tracker="bytetrack.yaml",
            verbose=False
        )[0]
        dt = (time.perf_counter() - t0) * 1000.0  # ms
        latencies.append(dt)
        
        boxes = res.boxes.xyxy.cpu().numpy() if res.boxes else np.array([])
        confs = res.boxes.conf.cpu().numpy() if res.boxes else np.array([])
        tids = res.boxes.id.int().cpu().numpy() if (res.boxes and res.boxes.id is not None) else []
        
        det_count = len(boxes)
        detection_counts.append(det_count)
        if det_count == 0:
            frames_zero_detections += 1
            
        for c in confs:
            all_confs.append(float(c))
        for tid in tids:
            unique_ids.add(int(tid))
            
        per_frame_details.append({
            "frame_idx": f_num,
            "detection_count": det_count,
            "latency_ms": round(dt, 2),
            "mean_conf": round(float(np.mean(confs)), 4) if len(confs) > 0 else 0.0,
            "track_ids": [int(x) for x in tids]
        })
        
        # Save annotated image if in sample indices
        if f_num in save_annot_indices:
            annot_img = draw_annotations(frame, boxes, confs, tids, model_name, cam_name, f_num, dt)
            save_path = os.path.join(out_img_dir, f"frame_{f_num:04d}.jpg")
            cv2.imwrite(save_path, annot_img)
            print(f"  [SAVED] {save_path} ({det_count} detections)")
            
    avg_lat = float(np.mean(latencies))
    fps = 1000.0 / avg_lat if avg_lat > 0 else 0.0
    
    stats = {
        "model_name": model_name,
        "model_path": os.path.relpath(model_path, PROJECT_ROOT),
        "total_frames_evaluated": len(frames),
        "total_detections": int(sum(detection_counts)),
        "avg_detections_per_frame": round(float(np.mean(detection_counts)), 2),
        "max_detections_in_one_frame": int(max(detection_counts)) if detection_counts else 0,
        "min_detections_in_one_frame": int(min(detection_counts)) if detection_counts else 0,
        "avg_confidence": round(float(np.mean(all_confs)), 4) if all_confs else 0.0,
        "min_confidence": round(float(np.min(all_confs)), 4) if all_confs else 0.0,
        "max_confidence": round(float(np.max(all_confs)), 4) if all_confs else 0.0,
        "unique_track_ids": len(unique_ids),
        "avg_latency_ms": round(avg_lat, 2),
        "median_latency_ms": round(float(np.median(latencies)), 2),
        "p95_latency_ms": round(float(np.percentile(latencies, 95)), 2),
        "approx_fps": round(fps, 1),
        "zero_detection_frames": frames_zero_detections,
        "per_frame_details": per_frame_details
    }
    return stats

def calc_pct_change(val_new, val_old):
    if val_old == 0:
        return 0.0 if val_new == 0 else 100.0
    return round(((val_new - val_old) / val_old) * 100.0, 2)

def main():
    print("==================================================")
    print(" CrowdShield A/B Model Benchmark: YOLOv8n vs person_best.pt")
    print("==================================================")
    
    # 1. Load Frames
    print("\n[STEP 1] Loading video frames...")
    cam1_frames, cam1_indices = load_frames(VIDEO_CAM1, CAM1_START_FRAME, FRAME_SAMPLE_COUNT)
    cam2_frames, cam2_indices = load_frames(VIDEO_CAM2, CAM2_START_FRAME, FRAME_SAMPLE_COUNT)
    
    # Select 4 representative frames for side-by-side saving
    cam1_save_indices = [cam1_indices[5], cam1_indices[25], cam1_indices[50], cam1_indices[75]]
    cam2_save_indices = [cam2_indices[5], cam2_indices[25], cam2_indices[50], cam2_indices[75]]
    print(f"CAM1 Save Indices: {cam1_save_indices}")
    print(f"CAM2 Save Indices: {cam2_save_indices}")
    
    # 2. Benchmark CAM1
    print("\n[STEP 2] Running CAM1 Benchmark...")
    print("  -> Evaluating YOLOv8n on CAM1...")
    cam1_v8_dir = os.path.join(BENCHMARK_DIR, "cam1", "yolov8n")
    cam1_v8_stats = evaluate_model_on_frames(MODEL_YOLOV8N, "YOLOv8n", cam1_frames, cam1_indices, cam1_save_indices, cam1_v8_dir, "cam1")
    
    print("  -> Evaluating person_best on CAM1...")
    cam1_pb_dir = os.path.join(BENCHMARK_DIR, "cam1", "person_best")
    cam1_pb_stats = evaluate_model_on_frames(MODEL_PERSON_BEST, "person_best.pt", cam1_frames, cam1_indices, cam1_save_indices, cam1_pb_dir, "cam1")
    
    # 3. Benchmark CAM2
    print("\n[STEP 3] Running CAM2 Benchmark...")
    print("  -> Evaluating YOLOv8n on CAM2...")
    cam2_v8_dir = os.path.join(BENCHMARK_DIR, "cam2", "yolov8n")
    cam2_v8_stats = evaluate_model_on_frames(MODEL_YOLOV8N, "YOLOv8n", cam2_frames, cam2_indices, cam2_save_indices, cam2_v8_dir, "cam2")
    
    print("  -> Evaluating person_best on CAM2...")
    cam2_pb_dir = os.path.join(BENCHMARK_DIR, "cam2", "person_best")
    cam2_pb_stats = evaluate_model_on_frames(MODEL_PERSON_BEST, "person_best.pt", cam2_frames, cam2_indices, cam2_save_indices, cam2_pb_dir, "cam2")
    
    # 4. Calculate Percentage Changes
    cam1_comparison = {
        "avg_detections_per_frame": {
            "yolov8n": cam1_v8_stats["avg_detections_per_frame"],
            "person_best": cam1_pb_stats["avg_detections_per_frame"],
            "pct_change": calc_pct_change(cam1_pb_stats["avg_detections_per_frame"], cam1_v8_stats["avg_detections_per_frame"])
        },
        "max_detections_in_one_frame": {
            "yolov8n": cam1_v8_stats["max_detections_in_one_frame"],
            "person_best": cam1_pb_stats["max_detections_in_one_frame"],
            "pct_change": calc_pct_change(cam1_pb_stats["max_detections_in_one_frame"], cam1_v8_stats["max_detections_in_one_frame"])
        },
        "avg_confidence": {
            "yolov8n": cam1_v8_stats["avg_confidence"],
            "person_best": cam1_pb_stats["avg_confidence"],
            "pct_change": calc_pct_change(cam1_pb_stats["avg_confidence"], cam1_v8_stats["avg_confidence"])
        },
        "unique_track_ids": {
            "yolov8n": cam1_v8_stats["unique_track_ids"],
            "person_best": cam1_pb_stats["unique_track_ids"],
            "pct_change": calc_pct_change(cam1_pb_stats["unique_track_ids"], cam1_v8_stats["unique_track_ids"])
        },
        "avg_latency_ms": {
            "yolov8n": cam1_v8_stats["avg_latency_ms"],
            "person_best": cam1_pb_stats["avg_latency_ms"],
            "pct_change": calc_pct_change(cam1_pb_stats["avg_latency_ms"], cam1_v8_stats["avg_latency_ms"])
        },
        "approx_fps": {
            "yolov8n": cam1_v8_stats["approx_fps"],
            "person_best": cam1_pb_stats["approx_fps"],
            "pct_change": calc_pct_change(cam1_pb_stats["approx_fps"], cam1_v8_stats["approx_fps"])
        },
        "zero_detection_frames": {
            "yolov8n": cam1_v8_stats["zero_detection_frames"],
            "person_best": cam1_pb_stats["zero_detection_frames"],
            "diff": cam1_pb_stats["zero_detection_frames"] - cam1_v8_stats["zero_detection_frames"]
        }
    }
    
    cam2_comparison = {
        "avg_detections_per_frame": {
            "yolov8n": cam2_v8_stats["avg_detections_per_frame"],
            "person_best": cam2_pb_stats["avg_detections_per_frame"],
            "pct_change": calc_pct_change(cam2_pb_stats["avg_detections_per_frame"], cam2_v8_stats["avg_detections_per_frame"])
        },
        "max_detections_in_one_frame": {
            "yolov8n": cam2_v8_stats["max_detections_in_one_frame"],
            "person_best": cam2_pb_stats["max_detections_in_one_frame"],
            "pct_change": calc_pct_change(cam2_pb_stats["max_detections_in_one_frame"], cam2_v8_stats["max_detections_in_one_frame"])
        },
        "avg_confidence": {
            "yolov8n": cam2_v8_stats["avg_confidence"],
            "person_best": cam2_pb_stats["avg_confidence"],
            "pct_change": calc_pct_change(cam2_pb_stats["avg_confidence"], cam2_v8_stats["avg_confidence"])
        },
        "unique_track_ids": {
            "yolov8n": cam2_v8_stats["unique_track_ids"],
            "person_best": cam2_pb_stats["unique_track_ids"],
            "pct_change": calc_pct_change(cam2_pb_stats["unique_track_ids"], cam2_v8_stats["unique_track_ids"])
        },
        "avg_latency_ms": {
            "yolov8n": cam2_v8_stats["avg_latency_ms"],
            "person_best": cam2_pb_stats["avg_latency_ms"],
            "pct_change": calc_pct_change(cam2_pb_stats["avg_latency_ms"], cam2_v8_stats["avg_latency_ms"])
        },
        "approx_fps": {
            "yolov8n": cam2_v8_stats["approx_fps"],
            "person_best": cam2_pb_stats["approx_fps"],
            "pct_change": calc_pct_change(cam2_pb_stats["approx_fps"], cam2_v8_stats["approx_fps"])
        },
        "zero_detection_frames": {
            "yolov8n": cam2_v8_stats["zero_detection_frames"],
            "person_best": cam2_pb_stats["zero_detection_frames"],
            "diff": cam2_pb_stats["zero_detection_frames"] - cam2_v8_stats["zero_detection_frames"]
        }
    }
    
    # Save report.json
    full_report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "settings": {
            "imgsz": IMGSZ,
            "conf": CONF_THRESH,
            "classes": CLASSES,
            "frames_per_camera": FRAME_SAMPLE_COUNT,
            "tracker": "bytetrack.yaml"
        },
        "cam1": {
            "video": os.path.basename(VIDEO_CAM1),
            "start_frame": CAM1_START_FRAME,
            "yolov8n": {k: v for k, v in cam1_v8_stats.items() if k != "per_frame_details"},
            "person_best": {k: v for k, v in cam1_pb_stats.items() if k != "per_frame_details"},
            "comparison": cam1_comparison
        },
        "cam2": {
            "video": os.path.basename(VIDEO_CAM2),
            "start_frame": CAM2_START_FRAME,
            "yolov8n": {k: v for k, v in cam2_v8_stats.items() if k != "per_frame_details"},
            "person_best": {k: v for k, v in cam2_pb_stats.items() if k != "per_frame_details"},
            "comparison": cam2_comparison
        }
    }
    
    os.makedirs(BENCHMARK_DIR, exist_ok=True)
    report_json_path = os.path.join(BENCHMARK_DIR, "report.json")
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2)
    print(f"\n[REPORT SAVED] {report_json_path}")
    
    # Mirror into CrowdShield_Shaurya/benchmark as well
    cs_bench_dir = os.path.join(PROJECT_ROOT, "CrowdShield_Shaurya", "benchmark")
    os.makedirs(cs_bench_dir, exist_ok=True)
    with open(os.path.join(cs_bench_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2)
        
    print("\n==================================================")
    print("CAM1 Summary:")
    print(f"  YOLOv8n:     avg_det={cam1_v8_stats['avg_detections_per_frame']}, max_det={cam1_v8_stats['max_detections_in_one_frame']}, conf={cam1_v8_stats['avg_confidence']}, track_ids={cam1_v8_stats['unique_track_ids']}, latency={cam1_v8_stats['avg_latency_ms']}ms, fps={cam1_v8_stats['approx_fps']}")
    print(f"  person_best: avg_det={cam1_pb_stats['avg_detections_per_frame']}, max_det={cam1_pb_stats['max_detections_in_one_frame']}, conf={cam1_pb_stats['avg_confidence']}, track_ids={cam1_pb_stats['unique_track_ids']}, latency={cam1_pb_stats['avg_latency_ms']}ms, fps={cam1_pb_stats['approx_fps']}")
    print(f"  Delta (%):   avg_det={cam1_comparison['avg_detections_per_frame']['pct_change']}%, conf={cam1_comparison['avg_confidence']['pct_change']}%, latency={cam1_comparison['avg_latency_ms']['pct_change']}%")

    print("\nCAM2 Summary:")
    print(f"  YOLOv8n:     avg_det={cam2_v8_stats['avg_detections_per_frame']}, max_det={cam2_v8_stats['max_detections_in_one_frame']}, conf={cam2_v8_stats['avg_confidence']}, track_ids={cam2_v8_stats['unique_track_ids']}, latency={cam2_v8_stats['avg_latency_ms']}ms, fps={cam2_v8_stats['approx_fps']}")
    print(f"  person_best: avg_det={cam2_pb_stats['avg_detections_per_frame']}, max_det={cam2_pb_stats['max_detections_in_one_frame']}, conf={cam2_pb_stats['avg_confidence']}, track_ids={cam2_pb_stats['unique_track_ids']}, latency={cam2_pb_stats['avg_latency_ms']}ms, fps={cam2_pb_stats['approx_fps']}")
    print(f"  Delta (%):   avg_det={cam2_comparison['avg_detections_per_frame']['pct_change']}%, conf={cam2_comparison['avg_confidence']['pct_change']}%, latency={cam2_comparison['avg_latency_ms']['pct_change']}%")
    print("==================================================")

if __name__ == "__main__":
    main()
