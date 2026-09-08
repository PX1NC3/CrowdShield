# CrowdShield Model A/B Benchmark Report: Vehicle Detection

**Date:** 2026-09-09  
**Models Evaluated:** Current Production Model (`yolov8n.pt`) vs Vishant's Vehicle Model (`vehicle_checkpoint.pt`)  
**Evaluation Scope:** Exact matching 80 active frames on both production cameras (CAM1 & CAM2) under matched inference conditions.  
**Production Integrity:** 100% Unaltered. Existing detection pipeline, `yolov8n.pt`, frontend, heatmap, ByteTrack person tracking, and APIs remain untouched.

---

## 1. Executive Summary

| Camera Perspective | Metric | Current: YOLOv8n (Vehicle Classes) | New: vehicle_checkpoint.pt | Delta (%) | Key Finding |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CAM1** *(Pedestrian Walkway overlooking Roadway)* | Total Detections (80 f) | 308 | **620** | **+101.30%** | Detects distant tiny parked cars along the horizon |
| | Avg Detections / Frame | 3.85 | **7.75** | **+101.30%** | Higher sensitivity on small background vehicles |
| | Max Detections / Frame | 7 | **10** | **+42.86%** | Captures distant parked vehicle line |
| | Avg Confidence | **0.6639** | 0.5017 | **-24.43%** | Lower confidence across all vehicle classes |
| | Unique Track IDs (80 f) | 15 | 18 | +20.00% | Stable tracking on static parked & moving cars |
| | Latency / Approx FPS | 104.1 ms (9.6 FPS) | **91.1 ms (11.0 FPS)** | **-12.45% / +14.58%** | Slightly faster due to fewer output class channels |
| **CAM2** *(Aerial Pedestrian Plaza — ZERO Vehicles)* | Total Detections (80 f) | **0** | 54 | +100% | ❌ **All 54 detections are FALSE POSITIVES** |
| | Avg Detections / Frame | **0.00** | 0.68 | +100% | Misclassifies pedestrians & shadows as vehicles |
| | Max Detections / Frame | **0** | 4 | +100% | Up to 4 phantom vehicles on pedestrian plaza |
| | Avg Confidence | 0.0000 | 0.3777 | N/A | Low-confidence phantom detections ($0.25 - 0.38$) |
| | Zero-Detection Frames | **80 / 80 (100%)** | 45 / 80 (56.3%) | -35 frames | YOLOv8n has 100% true negative accuracy |
| | Latency / Approx FPS | 92.8 ms (10.8 FPS) | 91.3 ms (10.9 FPS) | -1.64% / +0.93% | Comparable latency |

---

## 2. STEP 1 — Model Inspection: `vehicle_checkpoint.pt`

Before conducting inference, `vehicle_checkpoint.pt` was inspected with Ultralytics YOLO:

```python
Model: vehicle_checkpoint.pt
Architecture: YOLOv8 Nano (Custom Vehicle Head)
Parameters: 3,011,628 (~3.01 Million Parameters)
Weights Size: 23.34 MB (Unpruned FP32 checkpoint)
Task: detect
Number of Classes: 4
```

### Complete Class Mapping:
- **Class ID 0:** `'car'`
- **Class ID 1:** `'truck'`
- **Class ID 2:** `'bus'`
- **Class ID 3:** `'motorcycle'`

### Matched YOLOv8n COCO Vehicle Classes:
In the 80-class COCO taxonomy of `yolov8n.pt`, the corresponding vehicle classes are:
- **Class ID 2:** `'car'`
- **Class ID 3:** `'motorcycle'`
- **Class ID 5:** `'bus'`
- **Class ID 7:** `'truck'`

*(Class 1 `'bicycle'` was excluded to evaluate motorized vehicular traffic directly).*

---

## 3. STEP 2 & 3 — Benchmark Setup & Inference Settings

Both models were evaluated sequentially on the **exact same frames** using matched inference settings:
- `imgsz = 960`
- `conf = 0.25`
- Tracker: ByteTrack (`bytetrack.yaml`, `persist=True`)
- Evaluated Frames: **80 consecutive active frames per camera** (total 320 full inferences)
  - **CAM1 (`crowd_test.mp4`):** Frames **130 to 209**
  - **CAM2 (`stock-footage-busy-pedestrian-street-crowd-...webm`):** Frames **20 to 99**

---

## 4. STEP 4 — Quantitative Benchmark Results

### 4.1 CAM1: Ground-Level Corridor & Distant Roadway

| Metric | Current: YOLOv8n | New: vehicle_checkpoint.pt | Absolute Delta | Percentage Change |
| :--- | :--- | :--- | :--- | :--- |
| **Total Detections (80 frames)** | 308 | **620** | +312 | **+101.30%** |
| **Average Detections / Frame** | 3.85 | **7.75** | +3.90 | **+101.30%** |
| **Maximum Detections / Frame** | 7 | **10** | +3 | **+42.86%** |
| **Minimum Detections / Frame** | 2 | 6 | +4 | +200.00% |
| **Average Confidence** | **0.6639** | 0.5017 | -0.1622 | **-24.43%** |
| **Minimum Confidence Detected** | 0.2644 | 0.2502 | -0.0142 | -5.37% |
| **Maximum Confidence Detected** | **0.9546** | 0.7804 | -0.1742 | -18.25% |
| **Unique ByteTrack IDs** | 15 | **18** | +3 | **+20.00%** |
| **Zero-Detection Frames** | 0 | 0 | 0 | Identical (0%) |
| **Average Latency / Frame** | 104.09 ms | **91.13 ms** | -12.96 ms | **-12.45%** |
| **Median Latency** | 99.83 ms | **88.84 ms** | -10.99 ms | -11.01% |
| **95th Percentile Latency (p95)** | 146.81 ms | **112.99 ms** | -33.82 ms | -23.04% |
| **Approximate FPS** | 9.6 FPS | **11.0 FPS** | +1.4 FPS | **+14.58%** |

#### Per-Class Detection Breakdown on CAM1:
- **`yolov8n.pt`**:
  - `car`: 117 detections (mean conf **0.7547**, max 0.9546)
  - `truck`: 103 detections (mean conf 0.5677, max 0.8229)
  - `bus`: 88 detections (mean conf **0.6557**, max 0.8289)
  - `motorcycle`: 0 detections
- **`vehicle_checkpoint.pt`**:
  - `car`: **521 detections** (mean conf 0.5108, max 0.7804)
  - `truck`: 86 detections (mean conf 0.4679, max 0.6523)
  - `bus`: **0 detections** (completely misses or misclassifies buses as trucks/cars)
  - `motorcycle`: 13 detections (mean conf 0.3574, max 0.5258)

---

### 4.2 CAM2: Aerial Pedestrian Plaza (Ground Truth = ZERO Vehicles)

| Metric | Current: YOLOv8n | New: vehicle_checkpoint.pt | Absolute Delta | Percentage Change |
| :--- | :--- | :--- | :--- | :--- |
| **Total Detections (80 frames)** | **0** | 54 | +54 | **+100.0% (False Positives)** |
| **Average Detections / Frame** | **0.00** | 0.68 | +0.68 | N/A |
| **Maximum Detections / Frame** | **0** | 4 | +4 | N/A |
| **Minimum Detections / Frame** | 0 | 0 | 0 | N/A |
| **Average Confidence** | 0.0000 | 0.3777 | +0.3777 | Low marginal confidence |
| **Zero-Detection Frames** | **80 / 80 (100%)** | 45 / 80 (56.3%) | -35 | **43.7% of frames have ghost vehicles** |
| **Unique ByteTrack IDs** | **0** | 9 | +9 | Phantom tracks spawned |
| **Average Latency / Frame** | 92.85 ms | **91.33 ms** | -1.52 ms | -1.64% |
| **Approximate FPS** | 10.8 FPS | **10.9 FPS** | +0.1 FPS | +0.93% |

#### Per-Class Detection Breakdown on CAM2:
- **`yolov8n.pt`**:
  - 0 vehicles detected across all 80 frames (100% precision).
- **`vehicle_checkpoint.pt`**:
  - `car`: 44 false detections (mean conf 0.3852)
  - `motorcycle`: 10 false detections (mean conf 0.3445)
  - `bus`: 0 detections
  - `truck`: 0 detections

---

## 5. STEP 5 — Qualitative Visual Observations

Representative annotated comparison frames were generated with identical frame numbers and saved under `benchmark_vehicle/`:

### 5.1 CAM1: Ground-Level Walkway (`crowd_test.mp4`)
- **Annotated Frames:**
  - Frame 135: [yolov8n/frame_0135.jpg](file:///c:/Users/Pragyan%20Mishra/Desktop/CrowdShield/benchmark_vehicle/cam1/yolov8n/frame_0135.jpg) vs [vehicle_checkpoint/frame_0135.jpg](file:///c:/Users/Pragyan%20Mishra/Desktop/CrowdShield/benchmark_vehicle/cam1/vehicle_checkpoint/frame_0135.jpg)
  - Frame 155: [yolov8n/frame_0155.jpg](file:///c:/Users/Pragyan%20Mishra/Desktop/CrowdShield/benchmark_vehicle/cam1/yolov8n/frame_0155.jpg) vs [vehicle_checkpoint/frame_0155.jpg](file:///c:/Users/Pragyan%20Mishra/Desktop/CrowdShield/benchmark_vehicle/cam1/vehicle_checkpoint/frame_0155.jpg)
  - Frame 180: [yolov8n/frame_0180.jpg](file:///c:/Users/Pragyan%20Mishra/Desktop/CrowdShield/benchmark_vehicle/cam1/yolov8n/frame_0180.jpg) vs [vehicle_checkpoint/frame_0180.jpg](file:///c:/Users/Pragyan%20Mishra/Desktop/CrowdShield/benchmark_vehicle/cam1/vehicle_checkpoint/frame_0180.jpg)
  - Frame 205: [yolov8n/frame_0205.jpg](file:///c:/Users/Pragyan%20Mishra/Desktop/CrowdShield/benchmark_vehicle/cam1/yolov8n/frame_0205.jpg) vs [vehicle_checkpoint/frame_0205.jpg](file:///c:/Users/Pragyan%20Mishra/Desktop/CrowdShield/benchmark_vehicle/cam1/vehicle_checkpoint/frame_0205.jpg)

#### Detailed Analysis:
1. **Distant Small Vehicle Sensitivity:**
   - In CAM1, along the distant upper horizon (`x: 1600–1900, y: 0–40`), there is a row of parked cars (~33×35 pixels).
   - `vehicle_checkpoint.pt` successfully detects 4 to 5 of these tiny distant parked cars on every single frame (`conf = 0.35 - 0.54`).
   - `yolov8n.pt` misses these distant cars entirely, focusing only on the foreground and midground vehicles.
2. **Foreground Vehicle Confidence & Classification:**
   - On the prominent foreground car (`x: 474, y: 313, 895×546`), `yolov8n.pt` scores **0.913 confidence**. `vehicle_checkpoint.pt` detects it as a car, but with lower confidence (**0.688**).
   - For the midground transit bus, `yolov8n.pt` correctly classifies it as `bus` (`conf = 0.758`). `vehicle_checkpoint.pt` has **0 bus detections** throughout all 80 frames—it misclassifies the bus as a `truck` or splits it into multiple overlapping boxes.
3. **Pedestrian Confusion (No False Positives on Walking Pedestrians):**
   - On CAM1, `vehicle_checkpoint.pt` did **not** mistake walking foreground pedestrians for vehicles. All detections were confined to actual vehicular objects on the roadway or horizon line.

---

### 5.2 CAM2: Aerial Pedestrian Plaza
- **Annotated Frames:**
  - Frame 25: [yolov8n/frame_0025.jpg](file:///c:/Users/Pragyan%20Mishra/Desktop/CrowdShield/benchmark_vehicle/cam2/yolov8n/frame_0025.jpg) vs [vehicle_checkpoint/frame_0025.jpg](file:///c:/Users/Pragyan%20Mishra/Desktop/CrowdShield/benchmark_vehicle/cam2/vehicle_checkpoint/frame_0025.jpg)
  - Frame 45: [yolov8n/frame_0045.jpg](file:///c:/Users/Pragyan%20Mishra/Desktop/CrowdShield/benchmark_vehicle/cam2/yolov8n/frame_0045.jpg) vs [vehicle_checkpoint/frame_0045.jpg](file:///c:/Users/Pragyan%20Mishra/Desktop/CrowdShield/benchmark_vehicle/cam2/vehicle_checkpoint/frame_0045.jpg)
  - Frame 70: [yolov8n/frame_0070.jpg](file:///c:/Users/Pragyan%20Mishra/Desktop/CrowdShield/benchmark_vehicle/cam2/yolov8n/frame_0070.jpg) vs [vehicle_checkpoint/frame_0070.jpg](file:///c:/Users/Pragyan%20Mishra/Desktop/CrowdShield/benchmark_vehicle/cam2/vehicle_checkpoint/frame_0070.jpg)
  - Frame 95: [yolov8n/frame_0095.jpg](file:///c:/Users/Pragyan%20Mishra/Desktop/CrowdShield/benchmark_vehicle/cam2/yolov8n/frame_0095.jpg) vs [vehicle_checkpoint/frame_0095.jpg](file:///c:/Users/Pragyan%20Mishra/Desktop/CrowdShield/benchmark_vehicle/cam2/vehicle_checkpoint/frame_0095.jpg)

#### Detailed Analysis:
1. **Ground Truth Context:**
   - CAM2 is a dedicated pedestrian square with cobblestone paving. There are **zero motor vehicles** present anywhere in the frame.
2. **False Positive Phenomenon in `vehicle_checkpoint.pt`:**
   - In 35 out of 80 frames (43.7%), `vehicle_checkpoint.pt` generated 1 to 4 false-positive vehicle detections (54 total false detections).
   - **What triggered the false detections?**
     - Two pedestrians walking close together casting elongated shadows were bounded as a 21×40 pixel `"car"` (`conf = 0.604` on Frame 26).
     - Circular paving stones and bench borders were falsely labeled as `"motorcycle"` (`conf = 0.26 - 0.34`).
3. **YOLOv8n Superior Discriminative Filtering:**
   - `yolov8n.pt` produced **0 false vehicle detections** across all 80 frames (100% true negative specificity). It correctly distinguishes between pedestrians/infrastructure and vehicles from high-angle perspectives.

---

## 6. STEP 6 — CrowdShield-Specific Architecture Evaluation

In CrowdShield's current multi-camera architecture:
- **Primary Signal:** Person detection $\to$ ByteTrack tracking $\to$ ground-plane density $\to$ spatial heatmap $\to$ adaptive anomaly risk engine.
- **Strict Prohibition Enforced:** Vehicle detections **must never** be fed into person counts, crowd density grids, venue heatmaps, or stampede risk scores.

### Potential Utility as a Secondary Signal:
1. **Emergency Egress Clearance:** Detecting if unauthorized vehicles park in designated pedestrian evacuation corridors or fire lanes.
2. **Vehicle / Crowd Encroachment:** Warning safety managers when vehicular traffic encroaches within critical proximity of pedestrian choke points.
3. **Traffic Congestion Context:** Informing venue operators of external traffic gridlock near venue entrance gates.

---

## 7. STEP 7 — Final Verdict & Clear Recommendation

### **Recommendation: D) Promising but needs more training/calibration**
*(with an operational verdict of **B (Useful as secondary vehicle intelligence)** on roadside cameras only)*

### Camera-Specific Conclusions:

#### CAM1 (Ground-Level / Roadside Overlook):
- **Verdict: C) Better than YOLOv8n for distant/small vehicle detection, BUT weaker on buses.**
- `vehicle_checkpoint.pt` demonstrated impressive recall on small, distant parked vehicles (+101% detection count) with fast latency (91 ms / 11 FPS). However, its complete omission of the `bus` class and lower foreground confidence (0.50 vs 0.66) indicate that its training dataset lacked large commercial buses.

#### CAM2 (High-Angle Aerial Pedestrian Plaza):
- **Verdict: A) Not useful for CAM2 (Generates false positive ghost vehicles).**
- In aerial pedestrian-only zones, `vehicle_checkpoint.pt` misidentifies walking pedestrians and casting shadows as cars and motorcycles (54 false positives). `yolov8n.pt` is significantly more reliable here with 0 false alarms.

---

### Integration Decision for Technova Prototype:
> **DO NOT integrate `vehicle_checkpoint.pt` into the active Technova prototype yet.**

#### Why?
1. **Primary Crowd Mission:** CrowdShield's core capability is pedestrian crowd density and stampede prevention. `vehicle_checkpoint.pt` does not detect persons.
2. **False Alarms in Pedestrian Zones:** If applied across all cameras, `vehicle_checkpoint.pt` would falsely report motor vehicles inside pedestrian-only plazas like CAM2.
3. **Class Imbalance:** It fails to detect buses, which are essential for venue transit hubs and emergency response access.

#### Next Steps for Vishant & ML Team:
1. **Add Negative Pedestrian Samples:** Fine-tune `vehicle_checkpoint.pt` with hard negative mining on aerial pedestrian crowds to eliminate pedestrian-to-vehicle false positives.
2. **Rebalance Bus Training:** Augment the dataset with transit and tour buses to restore the `bus` class recall.
3. **Secondary Feature Deployment:** Once calibrated, deploy as a separate, optional background task strictly for "Emergency Vehicle / Access Road Monitoring" on perimeter cameras.

---

## 8. STEP 8 — Production Integrity Verification

All production files remain 100% untouched:
- `models/yolov8n.pt`: **Unaltered** (active in production)
- `src/detection/detect.py`: **Unaltered**
- `frontend/`: **Unaltered**
- `src/location/`: **Unaltered**
- All artifacts strictly saved in `benchmark_vehicle/`.
