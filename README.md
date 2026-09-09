# CrowdShield — AI-Powered Real-Time Crowd Safety Platform

CrowdShield is an AI-driven crowd safety intelligence platform combining real-time camera analytics (multi-camera YOLOv8n tracking, spatial zone risk analysis, movement flow tracking, and adaptive baselines) with geographic location heatmaps (2D Leaflet, 3D Three.js digital twin) and role-based incident prevention.

## Architecture & Data Flow

```
Camera Feeds (CAM 1, CAM 2)
      │
      ▼
YOLOv8n Person Tracking (ByteTrack, imgsz=960, conf=0.25, classes=[0], persist=True)
      │
      ▼
Spatial 3×3 Zone Analysis (Z1–Z9 Density, Flow Transitions, Centroid Vectors)
      │
      ▼
Adaptive Baseline & Trend Engine (Z-score, Rolling Deviation)
      │
      ▼
Multi-Factor Risk & Prevention Engine (Root Cause Diagnostics, Dynamic Diversions)
      │
      ├───────────────────────────────┬───────────────────────────────┐
      ▼                               ▼                               ▼
Live Prevention API             MJPEG Video Streams             Location Aggregator
(Port 8765: /live_prevention)    (Port 8765: /stream)            (Port 8766: /api/heatmap)
      │                               │                               │
      └───────────────────────────────┴───────────────────────────────┘
                                      │
                                      ▼
                        Vite + React Unified Frontend
                         (Port 5173 - Manager & Public)
```

## Production Model Configuration

- **Model:** `models/yolov8n.pt`
- **Inference Parameters:**
  - `imgsz`: `960`
  - `conf`: `0.25`
  - `classes`: `[0]` (Person class only)
  - `persist`: `True`
  - `tracker`: `bytetrack.yaml`

## Quick Start

### 1. Launch All Services Together

Run the unified launcher from the project root:

```powershell
python start_crowdshield.py
```

or on Windows:
```cmd
start.bat
```

This automatically launches:
- **Camera Analytics Backend:** `http://127.0.0.1:8765`
- **Location Heatmap Server:** `http://127.0.0.1:8766`
- **Vite React Frontend:** `http://localhost:5173`

### 2. Manual Service Execution

If running services in individual terminals:

**Camera Analytics Backend:**
```powershell
python src/detection/detect.py
```

**Location Heatmap Server:**
```powershell
python src/location/location_server.py
```

**Frontend Application:**
```powershell
cd frontend
npm run dev
```

## System Features & Capabilities

- **Real Multi-Camera Feeds:** Automatic dynamic discovery of video streams in `data/videos/` (`CAM 1` and `CAM 2`).
- **Spatial 3×3 Grid:** Real-time crowd density distribution across zones Z1 through Z9.
- **Dynamic Flow & Trajectory Tracking:** Sub-pixel optical flow camera-motion compensation + ByteTrack centroid velocity vectors.
- **Adaptive Baseline:** Self-calibrating normal density estimation using exponential moving statistics.
- **Root Cause & Prevention Engine:** Immediate diversion paths, crowd dispersal routing, and early congestion alerts.
- **Interactive 2D/3D Heatmaps:** Integrated Leaflet 2D venue map + Three.js 3D venue mesh digital twin.
- **Role-Based Views:**
  - **Manager Role:** Full operational metrics, raw risk scores, access controls, and diagnostics.
  - **Public Role:** Non-alarming crowd status, waypoint guidance, and safe navigation paths.
- **LIVE & DEMO Modes:** Real-time video analysis toggleable into simulated incident lifecycles (`normal`, `buildup`, `critical`, `dispersal`).

## Automated Tests & Verification

From the project root:
- `python test_location_api.py` — Location aggregator and heatmap endpoints
- `python test_demo_mode.py` — LIVE/DEMO modes and role filtering
- `python test_step3_intelligence.py` — Intelligence and spatial tracking test suite
- `python test_step4_prevention.py` — Incident lifecycle, safety paths, and diversion logic
- `python test_step5_longrun.py` — Long-run stability test
- `python verify_camera_pipeline.py` — Real multi-camera video streaming verification
