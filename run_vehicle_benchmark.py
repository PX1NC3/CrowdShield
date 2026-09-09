"""
CrowdShield Model A/B Benchmark: Vehicle Detection
Evaluates YOLOv8n vs Vishant's vehicle_checkpoint.pt on CAM1 and CAM2.
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
BENCHMARK_DIR = os.path.join(PROJECT_ROOT, "benchmark_vehicle")

MODEL_YOLOV8N = os.path.join(PROJECT_ROOT, "models", "yolov8n.pt")
MODEL_VEHICLE = os.path.join(PROJECT_ROOT, "models", "vehicle_checkpoint.pt")

VIDEO_CAM1 = os.path.join(PROJECT_ROOT, "data", "videos", "crowd_test.mp4")
VIDEO_CAM2 = os.path.join(PROJECT_ROOT, "data", "videos", "stock-footage-busy-pedestrian-street-crowd-people-walking-on-around-city-square-view-from-the-top-aerial-shoot.webm")

IMGSZ = 960
CONF_THRESH = 0.25
FRAME_SAMPLE_COUNT = 80

CAM1_START_FRAME = 130
CAM2_START_FRAME = 20

# Vehicle class definitions
# YOLOv8n (COCO): 2: car, 3: motorcycle, 5: bus, 7: truck
YOLOV8N_VEHICLE_CLASSES = [2, 3, 5, 7]
# vehicle_checkpoint.pt: 0: car, 1: truck, 2: bus, 3: motorcycle
VEHICLE_CHECKPOINT_CLASSES = [0, 1, 2, 3]

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

def draw_vehicle_annotations(frame, boxes, confs, class_names, track_ids, model_name, cam_name, frame_idx, avg_lat):
    annotated = frame.copy()
    h, w = annotated.shape[:2]
    
    # Top banner
    cv2.rectangle(annotated, (0, 0), (w, 52), (18, 22, 34), -1)
    title = f"{cam_name.upper()} | Model: {model_name} | Frame #{frame_idx} | Vehicles: {len(boxes)} | Latency: {avg_lat:.1f}ms"
    cv2.putText(annotated, title, (16, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 210, 255), 2, cv2.LINE_AA)
    
    # Palette per vehicle class
    color_map = {
        "car": (0, 220, 255),         # Yellow-Cyan
        "truck": (50, 120, 255),       # Orange-Red
        "bus": (255, 140, 0),         # Deep Blue/Amber
        "motorcycle": (180, 100, 255) # Pink/Violet
    }
    
    for i, box in enumerate(boxes):
        x1, y1, x2, y2 = [int(v) for v in box]
        conf = confs[i]
        cname = class_names[i]
        tid = track_ids[i] if (track_ids is not None and len(track_ids) > i) else None
        
        color = color_map.get(cname.lower(), (0, 255, 128))
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        
        lbl = f"{cname}"
        if tid is not None:
            lbl += f" #{tid}"
        lbl += f" {conf:.2f}"
        
        (tw, th), _ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        cv2.rectangle(annotated, (x1, max(0, y1 - th - 6)), (x1 + tw + 6, y1), color, -1)
        cv2.putText(annotated, lbl, (x1 + 3, max(th, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
        
    return annotated

def evaluate_vehicle_model(model_path, model_name, filter_classes, frames, frame_indices, save_annot_indices, out_img_dir, cam_name):
    os.makedirs(out_img_dir, exist_ok=True)
    
    # Warmup
    model = YOLO(model_path)
    dummy = np.zeros((480, 640, 3), dtype=np.uint8)
    _ = model.track(dummy, imgsz=IMGSZ, conf=CONF_THRESH, classes=filter_classes, persist=True, tracker="bytetrack.yaml", verbose=False)
    
    # Reset tracker cleanly
    del model
    model = YOLO(model_path)
    
    latencies = []
    detection_counts = []
    all_confs = []
    unique_ids = set()
    frames_zero_detections = 0
    per_class_counts = {}
    per_class_confs = {}
    per_frame_details = []
    
    for idx, (frame, f_num) in enumerate(zip(frames, frame_indices)):
        t0 = time.perf_counter()
        res = model.track(
            frame,
            imgsz=IMGSZ,
            conf=CONF_THRESH,
            classes=filter_classes,
            persist=True,
            tracker="bytetrack.yaml",
            verbose=False
        )[0]
        dt = (time.perf_counter() - t0) * 1000.0
        latencies.append(dt)
        
        boxes = res.boxes.xyxy.cpu().numpy() if res.boxes else np.array([])
        confs = res.boxes.conf.cpu().numpy() if res.boxes else np.array([])
        tids = res.boxes.id.int().cpu().numpy() if (res.boxes and res.boxes.id is not None) else []
        c_indices = res.boxes.cls.int().cpu().numpy() if res.boxes else []
        c_names = [model.names[c] for c in c_indices]
        
        det_count = len(boxes)
        detection_counts.append(det_count)
        if det_count == 0:
            frames_zero_detections += 1
            
        for c, cname in zip(confs, c_names):
            all_confs.append(float(c))
            per_class_counts[cname] = per_class_counts.get(cname, 0) + 1
            if cname not in per_class_confs:
                per_class_confs[cname] = []
            per_class_confs[cname].append(float(c))
            
        for tid in tids:
            unique_ids.add(int(tid))
            
        per_frame_details.append({
            "frame_idx": f_num,
            "detection_count": det_count,
            "latency_ms": round(dt, 2),
            "classes": c_names,
            "confs": [round(float(x), 3) for x in confs],
            "track_ids": [int(x) for x in tids]
        })
        
        if f_num in save_annot_indices:
            annot_img = draw_vehicle_annotations(frame, boxes, confs, c_names, tids, model_name, cam_name, f_num, dt)
            save_path = os.path.join(out_img_dir, f"frame_{f_num:04d}.jpg")
            cv2.imwrite(save_path, annot_img)
            print(f"  [SAVED] {save_path} ({det_count} vehicles: {c_names})")
            
    avg_lat = float(np.mean(latencies))
    fps = 1000.0 / avg_lat if avg_lat > 0 else 0.0
    
    per_class_summary = {}
    for cname, count in per_class_counts.items():
        c_conf_list = per_class_confs.get(cname, [])
        per_class_summary[cname] = {
            "total_detections": count,
            "avg_confidence": round(float(np.mean(c_conf_list)), 4) if c_conf_list else 0.0,
            "min_confidence": round(float(np.min(c_conf_list)), 4) if c_conf_list else 0.0,
            "max_confidence": round(float(np.max(c_conf_list)), 4) if c_conf_list else 0.0,
        }
        
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
        "per_class_summary": per_class_summary,
        "per_frame_details": per_frame_details
    }
    return stats

def calc_pct_change(val_new, val_old):
    if val_old == 0:
        return 0.0 if val_new == 0 else 100.0
    return round(((val_new - val_old) / val_old) * 100.0, 2)

def main():
    print("==================================================")
    print(" STEP 1 — MODEL INSPECTION: vehicle_checkpoint.pt")
    print("==================================================")
    v_model = YOLO(MODEL_VEHICLE)
    print(f"Model Path: {MODEL_VEHICLE}")
    print(f"Task: {v_model.task}")
    print(f"Number of Classes: {len(v_model.names)}")
    print("Complete Class Mapping:")
    for cid, cname in v_model.names.items():
        print(f"  Class ID {cid}: '{cname}'")
        
    y_model = YOLO(MODEL_YOLOV8N)
    print("\nYOLOv8n Matched Vehicle Classes:")
    for cid in YOLOV8N_VEHICLE_CLASSES:
        print(f"  Class ID {cid}: '{y_model.names[cid]}'")
        
    print("\n==================================================")
    print(" STEP 2 & 3 — BENCHMARK RUNNER")
    print("==================================================")
    cam1_frames, cam1_indices = load_frames(VIDEO_CAM1, CAM1_START_FRAME, FRAME_SAMPLE_COUNT)
    cam2_frames, cam2_indices = load_frames(VIDEO_CAM2, CAM2_START_FRAME, FRAME_SAMPLE_COUNT)
    
    # Target frame numbers required by user:
    # CAM1: 135, 155, 180, 205
    # CAM2: 25, 45, 70, 95
    cam1_save_indices = [135, 155, 180, 205]
    cam2_save_indices = [25, 45, 70, 95]
    print(f"CAM1 Save Indices: {cam1_save_indices}")
    print(f"CAM2 Save Indices: {cam2_save_indices}")
    
    # Run CAM1
    print("\n[CAM1] Evaluating YOLOv8n (Vehicle Classes: car, motorcycle, bus, truck)...")
    cam1_v8_dir = os.path.join(BENCHMARK_DIR, "cam1", "yolov8n")
    cam1_v8_stats = evaluate_vehicle_model(
        MODEL_YOLOV8N, "YOLOv8n", YOLOV8N_VEHICLE_CLASSES,
        cam1_frames, cam1_indices, cam1_save_indices, cam1_v8_dir, "cam1"
    )
    
    print("\n[CAM1] Evaluating vehicle_checkpoint.pt (All 4 Vehicle Classes)...")
    cam1_veh_dir = os.path.join(BENCHMARK_DIR, "cam1", "vehicle_checkpoint")
    cam1_veh_stats = evaluate_vehicle_model(
        MODEL_VEHICLE, "vehicle_checkpoint.pt", VEHICLE_CHECKPOINT_CLASSES,
        cam1_frames, cam1_indices, cam1_save_indices, cam1_veh_dir, "cam1"
    )
    
    # Run CAM2
    print("\n[CAM2] Evaluating YOLOv8n (Vehicle Classes: car, motorcycle, bus, truck)...")
    cam2_v8_dir = os.path.join(BENCHMARK_DIR, "cam2", "yolov8n")
    cam2_v8_stats = evaluate_vehicle_model(
        MODEL_YOLOV8N, "YOLOv8n", YOLOV8N_VEHICLE_CLASSES,
        cam2_frames, cam2_indices, cam2_save_indices, cam2_v8_dir, "cam2"
    )
    
    print("\n[CAM2] Evaluating vehicle_checkpoint.pt (All 4 Vehicle Classes)...")
    cam2_veh_dir = os.path.join(BENCHMARK_DIR, "cam2", "vehicle_checkpoint")
    cam2_veh_stats = evaluate_vehicle_model(
        MODEL_VEHICLE, "vehicle_checkpoint.pt", VEHICLE_CHECKPOINT_CLASSES,
        cam2_frames, cam2_indices, cam2_save_indices, cam2_veh_dir, "cam2"
    )
    
    # Comparison metrics
    cam1_comparison = {
        "avg_detections_per_frame": {
            "yolov8n": cam1_v8_stats["avg_detections_per_frame"],
            "vehicle_checkpoint": cam1_veh_stats["avg_detections_per_frame"],
            "pct_change": calc_pct_change(cam1_veh_stats["avg_detections_per_frame"], cam1_v8_stats["avg_detections_per_frame"])
        },
        "max_detections_in_one_frame": {
            "yolov8n": cam1_v8_stats["max_detections_in_one_frame"],
            "vehicle_checkpoint": cam1_veh_stats["max_detections_in_one_frame"],
            "pct_change": calc_pct_change(cam1_veh_stats["max_detections_in_one_frame"], cam1_v8_stats["max_detections_in_one_frame"])
        },
        "avg_confidence": {
            "yolov8n": cam1_v8_stats["avg_confidence"],
            "vehicle_checkpoint": cam1_veh_stats["avg_confidence"],
            "pct_change": calc_pct_change(cam1_veh_stats["avg_confidence"], cam1_v8_stats["avg_confidence"])
        },
        "unique_track_ids": {
            "yolov8n": cam1_v8_stats["unique_track_ids"],
            "vehicle_checkpoint": cam1_veh_stats["unique_track_ids"],
            "pct_change": calc_pct_change(cam1_veh_stats["unique_track_ids"], cam1_v8_stats["unique_track_ids"])
        },
        "avg_latency_ms": {
            "yolov8n": cam1_v8_stats["avg_latency_ms"],
            "vehicle_checkpoint": cam1_veh_stats["avg_latency_ms"],
            "pct_change": calc_pct_change(cam1_veh_stats["avg_latency_ms"], cam1_v8_stats["avg_latency_ms"])
        },
        "approx_fps": {
            "yolov8n": cam1_v8_stats["approx_fps"],
            "vehicle_checkpoint": cam1_veh_stats["approx_fps"],
            "pct_change": calc_pct_change(cam1_veh_stats["approx_fps"], cam1_v8_stats["approx_fps"])
        },
        "zero_detection_frames": {
            "yolov8n": cam1_v8_stats["zero_detection_frames"],
            "vehicle_checkpoint": cam1_veh_stats["zero_detection_frames"],
            "diff": cam1_veh_stats["zero_detection_frames"] - cam1_v8_stats["zero_detection_frames"]
        }
    }
    
    cam2_comparison = {
        "avg_detections_per_frame": {
            "yolov8n": cam2_v8_stats["avg_detections_per_frame"],
            "vehicle_checkpoint": cam2_veh_stats["avg_detections_per_frame"],
            "pct_change": calc_pct_change(cam2_veh_stats["avg_detections_per_frame"], cam2_v8_stats["avg_detections_per_frame"])
        },
        "max_detections_in_one_frame": {
            "yolov8n": cam2_v8_stats["max_detections_in_one_frame"],
            "vehicle_checkpoint": cam2_veh_stats["max_detections_in_one_frame"],
            "pct_change": calc_pct_change(cam2_veh_stats["max_detections_in_one_frame"], cam2_v8_stats["max_detections_in_one_frame"])
        },
        "avg_confidence": {
            "yolov8n": cam2_v8_stats["avg_confidence"],
            "vehicle_checkpoint": cam2_veh_stats["avg_confidence"],
            "pct_change": calc_pct_change(cam2_veh_stats["avg_confidence"], cam2_v8_stats["avg_confidence"])
        },
        "unique_track_ids": {
            "yolov8n": cam2_v8_stats["unique_track_ids"],
            "vehicle_checkpoint": cam2_veh_stats["unique_track_ids"],
            "pct_change": calc_pct_change(cam2_veh_stats["unique_track_ids"], cam2_v8_stats["unique_track_ids"])
        },
        "avg_latency_ms": {
            "yolov8n": cam2_v8_stats["avg_latency_ms"],
            "vehicle_checkpoint": cam2_veh_stats["avg_latency_ms"],
            "pct_change": calc_pct_change(cam2_veh_stats["avg_latency_ms"], cam2_v8_stats["avg_latency_ms"])
        },
        "approx_fps": {
            "yolov8n": cam2_v8_stats["approx_fps"],
            "vehicle_checkpoint": cam2_veh_stats["approx_fps"],
            "pct_change": calc_pct_change(cam2_veh_stats["approx_fps"], cam2_v8_stats["approx_fps"])
        },
        "zero_detection_frames": {
            "yolov8n": cam2_v8_stats["zero_detection_frames"],
            "vehicle_checkpoint": cam2_veh_stats["zero_detection_frames"],
            "diff": cam2_veh_stats["zero_detection_frames"] - cam2_v8_stats["zero_detection_frames"]
        }
    }
    
    full_report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model_inspection": {
            "model_path": os.path.relpath(MODEL_VEHICLE, PROJECT_ROOT),
            "architecture": "YOLOv8 Nano (Custom Vehicle Head)",
            "num_classes": len(v_model.names),
            "classes": v_model.names,
            "yolov8n_matched_classes": {cid: y_model.names[cid] for cid in YOLOV8N_VEHICLE_CLASSES}
        },
        "settings": {
            "imgsz": IMGSZ,
            "conf": CONF_THRESH,
            "frames_per_camera": FRAME_SAMPLE_COUNT,
            "tracker": "bytetrack.yaml"
        },
        "cam1": {
            "video": os.path.basename(VIDEO_CAM1),
            "start_frame": CAM1_START_FRAME,
            "yolov8n": {k: v for k, v in cam1_v8_stats.items() if k != "per_frame_details"},
            "vehicle_checkpoint": {k: v for k, v in cam1_veh_stats.items() if k != "per_frame_details"},
            "comparison": cam1_comparison
        },
        "cam2": {
            "video": os.path.basename(VIDEO_CAM2),
            "start_frame": CAM2_START_FRAME,
            "yolov8n": {k: v for k, v in cam2_v8_stats.items() if k != "per_frame_details"},
            "vehicle_checkpoint": {k: v for k, v in cam2_veh_stats.items() if k != "per_frame_details"},
            "comparison": cam2_comparison
        }
    }
    
    os.makedirs(BENCHMARK_DIR, exist_ok=True)
    report_json_path = os.path.join(BENCHMARK_DIR, "report.json")
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2)
    print(f"\n[REPORT SAVED] {report_json_path}")
    
    # Mirror into CrowdShield_Shaurya/benchmark_vehicle as well
    cs_bench_dir = os.path.join(PROJECT_ROOT, "CrowdShield_Shaurya", "benchmark_vehicle")
    os.makedirs(cs_bench_dir, exist_ok=True)
    with open(os.path.join(cs_bench_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2)

if __name__ == "__main__":
    main()
