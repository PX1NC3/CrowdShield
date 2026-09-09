"""
Single-run Read-Only Audit of All Video Files in CrowdShield
"""
import os
import sys
import time
import json
import cv2
import numpy as np
import torch
torch.set_num_threads(1)

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
from ultralytics import YOLO

def audit_file(filepath, model, num_frames=100):
    filename = os.path.basename(filepath)
    cap = cv2.VideoCapture(filepath)
    if not cap.isOpened():
        print(f"Error opening {filepath}", flush=True)
        return

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    total_f = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    dur = total_f / fps if fps > 0 else 0.0
    frame_area = w * h

    print(f"\n=======================================================", flush=True)
    print(f" VIDEO FILE: {filename}", flush=True)
    print(f"=======================================================", flush=True)
    print(f" Resolution:   {w} x {h}", flush=True)
    print(f" Frame Rate:   {fps:.2f} FPS", flush=True)
    print(f" Total Frames: {total_f}", flush=True)
    print(f" Duration:     {dur:.2f} seconds", flush=True)

    counts = []
    confs = []
    area_pcts = []
    frames_with_det = 0
    unique_tracks = set()

    for f_idx in range(num_frames):
        ret, frame = cap.read()
        if not ret:
            break
        with torch.no_grad():
            res = model.track(frame, persist=True, imgsz=640, verbose=False)
        boxes = res[0].boxes
        p_count = 0
        if boxes is not None and len(boxes) > 0:
            for b in boxes:
                if int(b.cls[0].cpu().numpy()) == 0:
                    p_count += 1
                    conf = float(b.conf[0].cpu().numpy())
                    confs.append(conf)
                    xyxy = b.xyxy[0].cpu().numpy()
                    area = (xyxy[2]-xyxy[0]) * (xyxy[3]-xyxy[1])
                    area_pcts.append(area / frame_area * 100.0)
                    if b.id is not None:
                        unique_tracks.add(int(b.id[0].cpu().numpy()))

        counts.append(p_count)
        if p_count > 0:
            frames_with_det += 1

    cap.release()

    avg_p = float(np.mean(counts)) if counts else 0.0
    max_p = int(np.max(counts)) if counts else 0
    det_rate = (frames_with_det / len(counts) * 100.0) if counts else 0.0
    avg_c = float(np.mean(confs)) if confs else 0.0
    avg_area = float(np.mean(area_pcts)) if area_pcts else 0.0

    print(f"\n --- ANALYSIS METRICS ({len(counts)} frames evaluated) ---", flush=True)
    print(f" Frames with Detections: {frames_with_det} / {len(counts)} ({det_rate:.1f}%)", flush=True)
    print(f" Average Persons/Frame: {avg_p:.2f}", flush=True)
    print(f" Max Persons/Frame:     {max_p}", flush=True)
    print(f" Avg Detection Conf:    {avg_c:.3f}", flush=True)
    print(f" Avg Bbox Area:         {avg_area:.3f}% of frame area", flush=True)
    print(f" Unique Track IDs:      {len(unique_tracks)}", flush=True)

    return {
        "filename": filename,
        "width": w,
        "height": h,
        "fps": fps,
        "total_frames": total_f,
        "duration_sec": dur,
        "evaluated_frames": len(counts),
        "det_rate_pct": det_rate,
        "avg_persons": avg_p,
        "max_persons": max_p,
        "avg_conf": avg_c,
        "avg_bbox_area_pct": avg_area,
        "unique_tracks": len(unique_tracks)
    }

def main():
    model_path = os.path.join(PROJECT_ROOT, "models", "yolov8n.pt")
    model = YOLO(model_path)

    v1 = os.path.join(PROJECT_ROOT, "data", "videos", "crowd_test.mp4")
    v2 = os.path.join(PROJECT_ROOT, "data", "videos", "stock-footage-busy-pedestrian-street-crowd-people-walking-on-around-city-square-view-from-the-top-aerial-shoot.webm")

    r1 = audit_file(v1, model, num_frames=100)
    r2 = audit_file(v2, model, num_frames=100)

    print("\n" + "=" * 80, flush=True)
    print("        MULTI-VIDEO DETECTION GENERALIZATION COMPARISON TABLE       ", flush=True)
    print("=" * 80, flush=True)
    print(f"{'Metric':<30} | {'crowd_test.mp4':<22} | {'busy_pedestrian_square.webm':<22}", flush=True)
    print("-" * 80, flush=True)
    res1 = f"{r1['width']}x{r1['height']}"
    res2 = f"{r2['width']}x{r2['height']}"
    fps1 = f"{r1['fps']:.1f} FPS"
    fps2 = f"{r2['fps']:.1f} FPS"
    det1 = f"{r1['det_rate_pct']:.1f}%"
    det2 = f"{r2['det_rate_pct']:.1f}%"
    avg_p1 = f"{r1['avg_persons']:.2f}"
    avg_p2 = f"{r2['avg_persons']:.2f}"
    avg_c1 = f"{r1['avg_conf']:.3f}"
    avg_c2 = f"{r2['avg_conf']:.3f}"
    area1 = f"{r1['avg_bbox_area_pct']:.3f}%"
    area2 = f"{r2['avg_bbox_area_pct']:.3f}%"

    print(f"{'Resolution':<30} | {res1:<22} | {res2:<22}", flush=True)
    print(f"{'Frame Rate':<30} | {fps1:<22} | {fps2:<22}", flush=True)
    print(f"{'Frames Tested':<30} | {r1['evaluated_frames']:<22} | {r2['evaluated_frames']:<22}", flush=True)
    print(f"{'Detection Rate (% frames)':<30} | {det1:<22} | {det2:<22}", flush=True)
    print(f"{'Average Persons / Frame':<30} | {avg_p1:<22} | {avg_p2:<22}", flush=True)
    print(f"{'Maximum Persons / Frame':<30} | {r1['max_persons']:<22} | {r2['max_persons']:<22}", flush=True)
    print(f"{'Average Confidence':<30} | {avg_c1:<22} | {avg_c2:<22}", flush=True)
    print(f"{'Avg Bbox Area (% frame)':<30} | {area1:<22} | {area2:<22}", flush=True)
    print(f"{'Unique Track IDs (100 frames)':<30} | {r1['unique_tracks']:<22} | {r2['unique_tracks']:<22}", flush=True)
    print("=" * 80, flush=True)

if __name__ == "__main__":
    main()
