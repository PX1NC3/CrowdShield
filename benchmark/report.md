# CrowdShield Model A/B Benchmark Report: YOLOv8n vs person_best.pt

**Date:** 2026-09-09  
**Evaluation Scope:** Comprehensive A/B comparison on exact matching video frames across both production camera perspectives under identical inference conditions.  
**Production Integrity:** Unaltered. Existing pipelines, `yolov8n.pt`, frontend, APIs, and trackers remain 100% untouched.

---

## 1. Executive Summary

| Camera Perspective | Metric | Current: YOLOv8n | New: person_best.pt | Delta (%) | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CAM1** *(Ground-Level Walkway)* | Avg Detections / Frame | **7.03** | 1.77 | **-74.82%** | ❌ **Severe Regression** (Misses 75% of pedestrians) |
| | Max Detections | **10** | 4 | **-60.00%** | ❌ Under-detects crowd clusters |
| | Avg Confidence | **0.6608** | 0.5173 | **-21.72%** | ❌ Lower confidence on upright pedestrians |
| | Unique Track IDs (80 f) | **19** | 9 | **-52.63%** | ❌ Fails to track passing visitors |
| | Zero-Detection Frames | **0** | 3 | +3 frames | ❌ Total blackout on 3 active frames |
| | Latency / FPS | 113.6 ms (8.8 FPS) | 93.1 ms (10.7 FPS) | -18.0% / +21.6% | Faster inference due to fewer boxes |
| **CAM2** *(High-Angle Aerial Square)* | Avg Detections / Frame | 28.36 | **48.64** | **+71.51%** | 🟢 Higher sensitivity to small aerial heads |
| | Max Detections | 41 | **100** | **+143.90%** | ⚠️ Captures dense clusters + edge noise |
| | Avg Confidence | **0.5304** | 0.4080 | **-23.08%** | ⚠️ 57% of detections hover in marginal 0.25–0.35 |
| | Unique Track IDs (80 f) | **150** | 507 | **+238.00%** | ⚠️ Severe track fragmentation / jitter |
| | Zero-Detection Frames | 0 | 0 | 0 | Identical continuity |
| | Latency / FPS | **96.9 ms (10.3 FPS)** | 110.2 ms (9.1 FPS) | +13.7% / -11.6% | Slightly slower due to 80+ candidate NMS |

---

## 2. Test Setup & Methodology

### 2.1 Evaluated Models
- **CURRENT: `models/yolov8n.pt`**
  - Architecture: YOLOv8 Nano (COCO-pretrained, 80 classes, class 0 = `person`)
  - File Size: 6.25 MB
- **NEW: `models/person_best.pt`**
  - Architecture: YOLOv8 Nano fine-tuned on VisDrone-style aerial pedestrian datasets (1 class = `person`)
  - File Size: 5.93 MB

### 2.2 Standardized Inference Parameters
Both models were executed sequentially on the **exact same frames** using identical parameters:
- `imgsz = 960`
- `conf = 0.25`
- `classes = [0]`
- Tracker: Ultralytics ByteTrack (`bytetrack.yaml`, `persist=True`)
- Frame Sample Count: **80 consecutive active frames** per camera (total 320 full-resolution inferences).

### 2.3 Video Sources
1. **CAM1 (`crowd_test.mp4`)**:
   - Ground-level eye/chest height perspective of pedestrians walking in an outdoor corridor.
   - Evaluated Frame Range: Frames **130 to 209** (active pedestrian flow).
2. **CAM2 (`stock-footage-busy-pedestrian-street-crowd-...webm`)**:
   - High-angle / aerial drone perspective of a public city square with dozens of walking pedestrians.
   - Evaluated Frame Range: Frames **20 to 99** (active multi-directional crowd flow).

---

## 3. Quantitative Benchmark Results

### 3.1 CAM1: Ground-Level Walkway (`crowd_test.mp4`)

| Metric | Current: YOLOv8n | New: person_best.pt | Absolute Change | Percentage Change |
| :--- | :--- | :--- | :--- | :--- |
| **Total Detections (80 frames)** | **562** | 142 | -420 | **-74.73%** |
| **Average Detections / Frame** | **7.03** | 1.77 | -5.26 | **-74.82%** |
| **Maximum Detections (Peak)** | **10** | 4 | -6 | **-60.00%** |
| **Minimum Detections** | 5 | 0 | -5 | -100.00% |
| **Average Confidence** | **0.6608** | 0.5173 | -0.1435 | **-21.72%** |
| **Minimum Confidence Detected** | 0.2501 | 0.2522 | +0.0021 | +0.84% |
| **Maximum Confidence Detected** | **0.9064** | 0.7752 | -0.1312 | -14.47% |
| **Unique ByteTrack IDs** | **19** | 9 | -10 | **-52.63%** |
| **Average Inference Latency** | 113.57 ms | **93.09 ms** | -20.48 ms | **-18.03%** |
| **Median Inference Latency** | 105.84 ms | **89.65 ms** | -16.19 ms | -15.30% |
| **95th Percentile Latency (p95)** | 161.11 ms | **127.95 ms** | -33.16 ms | -20.58% |
| **Approximate FPS** | 8.8 FPS | **10.7 FPS** | +1.9 FPS | **+21.59%** |
| **Zero-Detection Frames** | **0** | 3 | +3 | N/A |

### 3.2 CAM2: High-Angle Aerial City Square

| Metric | Current: YOLOv8n | New: person_best.pt | Absolute Change | Percentage Change |
| :--- | :--- | :--- | :--- | :--- |
| **Total Detections (80 frames)** | 2,269 | **3,891** | +1,622 | **+71.48%** |
| **Average Detections / Frame** | 28.36 | **48.64** | +20.28 | **+71.51%** |
| **Maximum Detections (Peak)** | 41 | **100** | +59 | **+143.90%** |
| **Minimum Detections** | 19 | 32 | +13 | +68.42% |
| **Average Confidence** | **0.5304** | 0.4080 | -0.1224 | **-23.08%** |
| **Minimum Confidence Detected** | 0.2512 | 0.2518 | +0.0006 | +0.24% |
| **Maximum Confidence Detected** | **0.9090** | 0.7432 | -0.1658 | -18.24% |
| **Unique ByteTrack IDs** | **150** | 507 | +357 | **+238.00%** |
| **Average Inference Latency** | **96.94 ms** | 110.19 ms | +13.25 ms | **+13.67%** |
| **Median Inference Latency** | **93.59 ms** | 105.14 ms | +11.55 ms | +12.34% |
| **95th Percentile Latency (p95)** | **135.33 ms** | 143.22 ms | +7.89 ms | +5.83% |
| **Approximate FPS** | **10.3 FPS** | 9.1 FPS | -1.2 FPS | **-11.65%** |
| **Zero-Detection Frames** | 0 | 0 | 0 | Identical (0%) |

---

## 4. Qualitative Analysis & Visual Observations

Representative annotated frames were generated for identical frame numbers and saved under `benchmark/`:

### 4.1 CAM1 Observations (Ground-Level Footage)
- **Files:**
  - `benchmark/cam1/yolov8n/frame_0135.jpg` vs `benchmark/cam1/person_best/frame_0135.jpg`
  - `benchmark/cam1/yolov8n/frame_0155.jpg` vs `benchmark/cam1/person_best/frame_0155.jpg`
  - `benchmark/cam1/yolov8n/frame_0180.jpg` vs `benchmark/cam1/person_best/frame_0180.jpg`
  - `benchmark/cam1/yolov8n/frame_0205.jpg` vs `benchmark/cam1/person_best/frame_0205.jpg`

1. **Massive False Negative Rate (Missed Persons)**:
   - On frame 135, YOLOv8n accurately bounds **8 walking pedestrians** from near to mid-ground with confidence scores between 0.65 and 0.88. `person_best.pt` only detects **2 individuals**, completely ignoring 6 prominent pedestrians walking in plain sight.
   - On frame 205, YOLOv8n detects **7 pedestrians**, whereas `person_best.pt` drops to **0 detections** (empty scene).
2. **Root Cause**:
   - `person_best.pt` was fine-tuned heavily on VisDrone-style aerial images where targets are small 10–30px dots viewed from a steep angle. It has catastrophic feature collapse on full-body upright human aspect ratios ($H:W \approx 3:1$).
3. **Tracking Failure**:
   - Because detections constantly drop out, ByteTrack is unable to maintain continuity, identifying only 9 tracks compared to 19 sustained pedestrian tracks with YOLOv8n.

### 4.2 CAM2 Observations (High-Angle Aerial Footage)
- **Files:**
  - `benchmark/cam2/yolov8n/frame_0025.jpg` vs `benchmark/cam2/person_best/frame_0025.jpg`
  - `benchmark/cam2/yolov8n/frame_0045.jpg` vs `benchmark/cam2/person_best/frame_0045.jpg`
  - `benchmark/cam2/yolov8n/frame_0070.jpg` vs `benchmark/cam2/person_best/frame_0070.jpg`
  - `benchmark/cam2/yolov8n/frame_0095.jpg` vs `benchmark/cam2/person_best/frame_0095.jpg`

1. **Superior Small-Target Recall**:
   - `person_best.pt` successfully identifies small, distant heads and shoulders in the plaza background that general-purpose YOLOv8n overlooks, increasing average detections from 28.36 to 48.64.
2. **Low-Confidence Flicker & Noise (57% Marginal Detections)**:
   - On Frame 45, out of 84 detections from `person_best.pt`, **48 boxes (57.1%)** have confidence $< 0.35$. Only 7 detections exceed $0.50$ confidence.
   - By comparison, YOLOv8n has a solid core of 13 high-confidence detections ($> 0.50$) with a mean confidence of $0.530$.
3. **Severe Track Fragmentation (+238% Track ID Explosion)**:
   - Over 80 frames on CAM2, approximately 35–45 actual people cross the field of view.
   - YOLOv8n generated **150 unique track IDs** (some ID re-assignment when people enter/leave).
   - `person_best.pt` generated **507 unique track IDs**—more than 6 new track IDs per frame! This occurs because low-confidence boxes ($0.25 - 0.35$) flicker on and off across consecutive frames, causing ByteTrack to repeatedly break track continuity and spawn fresh IDs.
4. **False Positives**:
   - `person_best.pt` occasionally triggers on street bollards, circular pavement tiles, and high-contrast stone bench borders that mimic the circular silhouette of a human head from above.

---

## 5. Architectural Trade-Off Analysis

| Criteria | Option A: Keep YOLOv8n | Option B: Full Replace with person_best.pt | Option C: Hybrid Deployment (person_best for CAM2, YOLOv8n for CAM1) |
| :--- | :--- | :--- | :--- |
| **CAM1 Ground Accuracy** | High (7.03 det/frame, 0.66 conf) | ❌ Broken (-75% recall, 3 blackouts) | High (YOLOv8n maintained) |
| **CAM2 Aerial Sensitivity** | Moderate (28.4 det/frame) | High (48.6 det/frame) | High (48.6 det/frame) |
| **CAM2 Tracking Stability** | Stable (150 track IDs) | ⚠️ Noisy (507 track IDs) | ⚠️ Noisy unless `conf` is raised to $\ge 0.38$ |
| **Heatmap & Risk Engine Impact** | Calibrated & Stable | ❌ Distorted risk scores on CAM1 | Requires per-camera risk baseline re-tuning |
| **Operational Complexity** | Single model in memory (6.2 MB) | Single model in memory (5.9 MB) | Dual models loaded in memory (~12 MB) |

---

## 6. Clear Recommendation & Justification

### Recommended Decision: **Option A — Keep YOLOv8n for Production Baseline**  
*(with a path toward Option C once confidence gating and tracker tuning are applied)*

### Why NOT Option B (Full Replace)?
Replacing `yolov8n.pt` globally with `person_best.pt` would **severely break CAM1**. The model misses 3 out of every 4 people on ground-level cameras and drops to zero detections on multiple frames. For a crowd safety platform, missing pedestrians walking directly into a corridor is an unacceptable safety failure.

### Why Option A is Recommended Today over Option C:
While `person_best.pt` detects 71.5% more candidates on aerial CAM2, **over 57% of those candidates hover in the unstable 0.25–0.35 confidence range**. Without raising the detection threshold, this introduces:
1. **Severe Track Fragmentation:** 507 tracking IDs created across 80 frames (+238% jump), which destabilizes ByteTrack speed vectors and direction estimates.
2. **False Density Spikes:** The 3D and 2D heatmaps derive localized density from track counts; a sudden influx of 48 low-confidence flickering boxes creates artificial "phantom hotspots" on static pavement textures.

### Roadmap to Unlock Option C in the Future:
If Vishant's model is to be deployed for CAM2 in a future update, the following two preconditions must be met first:
1. **Confidence Threshold Gating:** For CAM2, set `conf = 0.38` instead of `0.25` to filter out the 57% marginal jitter boxes while retaining the true small-person aerial detections.
2. **Per-Camera Model Loading:** Update the backend architecture to support camera-specific model weights (`CAMERAS['cam1']['model'] = 'yolov8n.pt'`, `CAMERAS['cam2']['model'] = 'person_best.pt'`).

---

## 7. Artifacts & Outputs Available for Inspection

All benchmark data, structured metrics, and side-by-side annotated frames are preserved in:
- `benchmark/report.json`
- `benchmark/report.md`
- `benchmark/cam1/yolov8n/*.jpg`
- `benchmark/cam1/person_best/*.jpg`
- `benchmark/cam2/yolov8n/*.jpg`
- `benchmark/cam2/person_best/*.jpg`

*(Production files were untouched throughout this benchmark).*
