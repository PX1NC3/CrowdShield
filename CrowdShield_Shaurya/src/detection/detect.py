import os
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"

# Resolve project root relative to this script (src/detection/ -> project root)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", ".."))

import torch
torch.set_num_threads(1) # Limit PyTorch threads to prevent CPU thread contention

from ultralytics import YOLO
import cv2
import numpy as np
import csv
import json
import threading
import sys
# Ensure src directory is on sys.path
_SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import time
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from collections import deque

# Ensure demo_generator singleton instance is synchronized across all import paths
try:
    import demo_generator as _dg_mod
    sys.modules["src.demo_generator"] = _dg_mod
except ImportError:
    pass

# =====================================================
# DYNAMIC MULTI-CAMERA DISCOVERY
# =====================================================

def discover_cameras():
    videos_dir = os.path.join(PROJECT_ROOT, "data", "videos")
    cameras = {}
    valid_exts = {".mp4", ".webm", ".avi", ".mov", ".mkv"}

    if os.path.exists(videos_dir):
        files = sorted(os.listdir(videos_dir))
        vid_files = [f for f in files if os.path.splitext(f)[1].lower() in valid_exts]

        for idx, filename in enumerate(vid_files, start=1):
            cam_id = f"cam{idx}"
            full_path = os.path.join(videos_dir, filename)
            clean_name = os.path.splitext(filename)[0].replace("-", " ").replace("_", " ").title()
            if len(clean_name) > 25:
                clean_name = clean_name[:22] + "..."
            cameras[cam_id] = {
                "name": f"CAM {idx} - {clean_name}",
                "source": full_path
            }

    if not cameras:
        cameras["cam1"] = {
            "name": "CAM 1 - Default Feed",
            "source": os.path.join(PROJECT_ROOT, "data", "videos", "crowd_test.mp4")
        }

    return cameras

CAMERAS = discover_cameras()

log_folder = os.path.join(PROJECT_ROOT, "data", "logs")
os.makedirs(log_folder, exist_ok=True)

LIVE_PREVENTION_JSON = os.path.join(log_folder, "live_prevention.json")
LIVE_API_HOST = "127.0.0.1"
LIVE_API_PORT = 8765

# Thread-safe global state for all cameras
class CameraStateStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.jpegs = {cam: None for cam in CAMERAS}
        self.zone_states = {cam: {} for cam in CAMERAS}
        self.prevention_states = {cam: {} for cam in CAMERAS}
        self.density_history = {cam: deque(maxlen=60) for cam in CAMERAS}
        self.risk_history = {cam: deque(maxlen=60) for cam in CAMERAS}

state_store = CameraStateStore()

def get_demo_generator():
    """Dynamically retrieves the shared demo generator singleton instance."""
    try:
        import demo_generator as dg
        return dg.demo_generator
    except ImportError:
        try:
            from src import demo_generator as dg
            return dg.demo_generator
        except ImportError:
            return None

# =====================================================
# HTTP API SERVER
# =====================================================

class LivePreventionHandler(BaseHTTPRequestHandler):
    """HTTP handler for CrowdShield multi-camera endpoints (Live & Demo mode)."""

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def do_POST(self):
        dg = get_demo_generator()
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = {}
        if length > 0:
            try:
                body = json.loads(self.rfile.read(length))
            except Exception:
                body = {}

        # --------------------------------------------------
        # POST /api/demo/toggle (or /demo/toggle)
        # --------------------------------------------------
        if path in ("/api/demo/toggle", "/demo/toggle", "/api/camera/demo/toggle"):
            if dg:
                enabled = body.get("enabled")
                state = dg.toggle_camera(enabled)
                scenario = body.get("scenario")
                if scenario:
                    dg.set_scenario(scenario)
                payload = {
                    "status": "ok",
                    "demo_mode": state,
                    "demo_scenario": dg.scenario,
                    "target": "camera",
                }
            else:
                payload = {"status": "error", "message": "Demo generator not available"}

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))

        # --------------------------------------------------
        # POST /api/demo/scenario (or /demo/scenario)
        # --------------------------------------------------
        elif path in ("/api/demo/scenario", "/demo/scenario"):
            scenario = body.get("scenario", "buildup")
            if dg:
                curr = dg.set_scenario(scenario)
                payload = {"status": "ok", "demo_scenario": curr}
            else:
                payload = {"status": "error", "message": "Demo generator not available"}

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))

        else:
            self.send_response(404)
            self._cors_headers()
            self.end_headers()

    def do_GET(self):
        dg = get_demo_generator()
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        req_cam = query.get("cam", ["cam1"])[0].lower()
        role = query.get("role", ["manager"])[0].lower()
        forced_demo = query.get("demo", [None])[0]

        if req_cam not in CAMERAS:
            req_cam = list(CAMERAS.keys())[0]

        is_demo = (
            forced_demo == "1"
            or forced_demo == "true"
            or (dg is not None and dg.camera_enabled)
        )

        # --------------------------------------------------
        # GET /api/demo/status
        # --------------------------------------------------
        if path in ("/api/demo/status", "/demo/status"):
            payload = {
                "camera_demo": dg.camera_enabled if dg else False,
                "heatmap_demo": dg.heatmap_enabled if dg else False,
                "scenario": dg.scenario if dg else "normal",
                "scenarios_available": ["normal", "buildup", "critical", "dispersal"],
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(json.dumps(payload, indent=2).encode("utf-8"))
            return

        # --------------------------------------------------
        # Live prevention JSON (Multi-camera aware)
        # --------------------------------------------------
        if path in ("/", "/live_prevention.json", "/api/prevention"):
            if is_demo and dg:
                demo_data = dg.generate_camera_data(req_cam, user_role=role)
                payload = demo_data["prevention"]
            else:
                with state_store.lock:
                    cameras_summary = {}
                    active_threats = []
                    all_threats = []

                    for cid, cconfig in CAMERAS.items():
                        pstate = state_store.prevention_states.get(cid) or {}
                        cthreats = pstate.get("threats", [])
                        clevel = pstate.get("highest_risk_level", "LOW")
                        cpeople = pstate.get("total_people", 0)

                        cameras_summary[cid] = {
                            "name": cconfig["name"],
                            "risk_level": clevel,
                            "threat_count": len(cthreats),
                            "total_people": cpeople,
                            "has_serious_threat": clevel in ("HIGH", "CRITICAL")
                        }

                        if cid == req_cam:
                            active_threats = cthreats

                        all_threats.extend(cthreats)

                    req_pstate = state_store.prevention_states.get(req_cam) or {}

                    if role == "user":
                        # Strictly sanitized Public User guidance payload - NO risk_score, NO HIGH/CRITICAL, NO origin, NO stampede/alarm info
                        public_threats = []
                        for t in active_threats:
                            lvl = t.get("risk_level", "LOW")
                            c_status = "Crowded" if lvl in ("HIGH", "CRITICAL") else ("Moderate" if lvl == "MEDIUM" else "Low")
                            safe_alt = t.get("safe_alternative", "clear pathways")
                            public_threats.append({
                                "zone": t.get("zone"),
                                "crowd_status": c_status,
                                "safe_alternative": safe_alt,
                                "recommended_route": f"Use Zone {safe_alt} for smooth passage",
                                "safe_guidance": f"High foot-traffic in {t.get('zone')}. Recommended alternate: {safe_alt}.",
                                "safety_instruction": f"Follow directional signage toward {safe_alt}.",
                                "recommended_action": f"Walking route via {safe_alt} is currently clearer.",
                            })

                        highest_crowd = "Crowded" if any(t.get("crowd_status") == "Crowded" for t in public_threats) else ("Moderate" if any(t.get("crowd_status") == "Moderate" for t in public_threats) else "Low")

                        payload = {
                            "status": "active",
                            "role": "user",
                            "demo_mode": False,
                            "timestamp": datetime.now().isoformat(timespec="seconds"),
                            "active_camera": req_cam,
                            "overall_crowd_status": highest_crowd,
                            "guidance_notices": public_threats,
                            "cameras": {
                                cid: {
                                    "name": cconfig["name"],
                                    "crowd_status": "Crowded" if cameras_summary[cid]["risk_level"] in ("HIGH", "CRITICAL") else ("Moderate" if cameras_summary[cid]["risk_level"] == "MEDIUM" else "Low"),
                                    "notice": "Active monitoring",
                                }
                                for cid, cconfig in CAMERAS.items()
                            },
                            "threats": public_threats,
                            "public_safety_message": "Pedestrian paths are monitored for your safety. Follow navigation guides for the smoothest route.",
                        }
                    else:
                        # Full Manager Intelligence payload
                        payload = {
                            "status": "active",
                            "role": "manager",
                            "demo_mode": False,
                            "timestamp": datetime.now().isoformat(timespec="seconds"),
                            "active_camera": req_cam,
                            "threat_detected": len(active_threats) > 0,
                            "highest_risk_zone": req_pstate.get("highest_risk_zone"),
                            "highest_risk_level": req_pstate.get("highest_risk_level", "LOW"),
                            "total_people": req_pstate.get("total_people", 0),
                            "threat_count": len(active_threats),
                            "cameras": cameras_summary,
                            "threats": active_threats,
                            "all_threats": all_threats
                        }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(json.dumps(payload, indent=2).encode("utf-8"))

        # --------------------------------------------------
        # MJPEG stream for requested camera (Non-blocking update loop)
        # --------------------------------------------------
        elif path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=crowdframe")
            self._cors_headers()
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

            try:
                last_jpeg = None
                while True:
                    if is_demo and dg:
                        jpeg = dg.generate_demo_frame(req_cam)
                    else:
                        with state_store.lock:
                            jpeg = state_store.jpegs.get(req_cam)

                    # If no frame or duplicate frame, wait briefly and try again
                    if jpeg is None or jpeg == last_jpeg:
                        time.sleep(0.03)
                        continue

                    last_jpeg = jpeg
                    try:
                        self.wfile.write(
                            b"--crowdframe\r\n"
                            b"Content-Type: image/jpeg\r\n\r\n"
                            + jpeg
                            + b"\r\n"
                        )
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                        break
                    time.sleep(0.03)
            except Exception:
                pass

        # --------------------------------------------------
        # Per-zone state for requested camera
        # --------------------------------------------------
        elif path == "/zones":
            if is_demo and dg:
                demo_data = dg.generate_camera_data(req_cam, user_role=role)
                payload = json.dumps(demo_data["zones"], indent=2).encode("utf-8")
            else:
                with state_store.lock:
                    zstate = state_store.zone_states.get(req_cam) or {}
                    if role == "user":
                        # Sanitize zones for public users - remove trend math, delta, risk_score, causes
                        raw_zones = zstate.get("zones", [])
                        sanitized_zones = []
                        for z in raw_zones:
                            lvl = z.get("risk_level", "LOW")
                            c_status = "Crowded" if lvl in ("HIGH", "CRITICAL") else ("Moderate" if lvl == "MEDIUM" else "Low")
                            sanitized_zones.append({
                                "zone": z.get("zone"),
                                "crowd_status": c_status,
                                "nav_recommendation": "Clear walking path" if c_status == "Low" else ("Moderate foot traffic" if c_status == "Moderate" else "High activity — prefer alternate routes"),
                            })
                        public_zstate = {
                            "camera_id": req_cam,
                            "role": "user",
                            "demo_mode": False,
                            "timestamp": zstate.get("timestamp", datetime.now().isoformat(timespec="seconds")),
                            "zones": sanitized_zones,
                        }
                        payload = json.dumps(public_zstate, indent=2).encode("utf-8")
                    else:
                        zstate["demo_mode"] = False
                        zstate["role"] = "manager"
                        payload = json.dumps(zstate, indent=2).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        # --------------------------------------------------
        # Per-camera density and risk history snapshots
        # --------------------------------------------------
        elif path in ("/history/density", "/api/history/density"):
            with state_store.lock:
                records = list(state_store.density_history.get(req_cam, []))
            payload = json.dumps({"camera_id": req_cam, "history": records}, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        elif path in ("/history/risk", "/api/history/risk"):
            with state_store.lock:
                records = list(state_store.risk_history.get(req_cam, []))
            payload = json.dumps({"camera_id": req_cam, "history": records}, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        else:
            self.send_response(404)
            self._cors_headers()
            self.end_headers()

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format, *args):
        return

def start_live_api():
    server = ThreadingHTTPServer((LIVE_API_HOST, LIVE_API_PORT), LivePreventionHandler)
    server.daemon_threads = True
    server.serve_forever()

threading.Thread(target=start_live_api, daemon=True).start()

# =====================================================
# CAMERA PROCESSOR WORKER
# =====================================================

def run_camera_processor(cam_id: str, cam_name: str, video_source: str):
    model_path = os.path.join(PROJECT_ROOT, "models", "yolov8n.pt")
    if not os.path.exists(model_path):
        model_path = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", "models", "yolov8n.pt"))
    if not os.path.exists(model_path):
        model_path = "yolov8n.pt"  # ultralytics auto-download fallback
    model = YOLO(model_path)

    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        print(f"[{cam_id.upper()}] ERROR: Could not open {video_source}")
        return

    prev_gray = None
    camera_offset_x = 0
    camera_offset_y = 0

    previous_zones = {}
    zone_flows = {}

    previous_density = [0] * 9

    TREND_HISTORY_SIZE = 20
    TREND_THRESHOLD = 0.5

    density_history_buffer = [deque(maxlen=TREND_HISTORY_SIZE) for _ in range(9)]
    density_trends = ["STABLE"] * 9
    density_trend_delta = [0.0] * 9
    frame_counter = 0

    YOLO_IMGSZ = 960
    CAMERA_MOTION_INTERVAL = 3

    # Adaptive baselines per camera
    BASELINE_MIN_SAMPLES = 30
    BASELINE_WINDOW_SIZE = 120
    BASELINE_ALPHA = 0.05

    zone_baseline_mean = [None] * 9
    zone_baseline_std = [None] * 9
    zone_density_samples = [[] for _ in range(9)]

    flow_baseline_mean_in = [None] * 9
    flow_baseline_std_in = [None] * 9
    flow_baseline_mean_out = [None] * 9
    flow_baseline_std_out = [None] * 9
    flow_samples_in = [[] for _ in range(9)]
    flow_samples_out = [[] for _ in range(9)]

    def update_adaptive_baseline(densities):
        for i in range(9):
            val = float(densities[i])
            samples = zone_density_samples[i]
            samples.append(val)
            if len(samples) > BASELINE_WINDOW_SIZE:
                samples.pop(0)
            if len(samples) >= BASELINE_MIN_SAMPLES:
                mean = sum(samples) / len(samples)
                variance = sum((x - mean) ** 2 for x in samples) / len(samples)
                std = max(variance ** 0.5, 1.0)

                if zone_baseline_mean[i] is None:
                    zone_baseline_mean[i] = mean
                    zone_baseline_std[i] = std
                else:
                    zone_baseline_mean[i] = (1 - BASELINE_ALPHA) * zone_baseline_mean[i] + BASELINE_ALPHA * mean
                    zone_baseline_std[i] = (1 - BASELINE_ALPHA) * zone_baseline_std[i] + BASELINE_ALPHA * std

    def get_baseline_deviation(densities):
        devs = []
        for i in range(9):
            if zone_baseline_mean[i] is None:
                devs.append(0.0)
            else:
                devs.append((float(densities[i]) - zone_baseline_mean[i]) / max(zone_baseline_std[i], 1.0))
        return devs

    def update_flow_baselines(incoming, outgoing):
        for i in range(9):
            for values, samples_all, means, stds in [
                (incoming, flow_samples_in, flow_baseline_mean_in, flow_baseline_std_in),
                (outgoing, flow_samples_out, flow_baseline_mean_out, flow_baseline_std_out),
            ]:
                val = float(values[i])
                s = samples_all[i]
                s.append(val)
                if len(s) > BASELINE_WINDOW_SIZE:
                    s.pop(0)
                if len(s) >= BASELINE_MIN_SAMPLES:
                    m = sum(s) / len(s)
                    v = sum((x - m) ** 2 for x in s) / len(s)
                    sd = max(v ** 0.5, 1.0)
                    if means[i] is None:
                        means[i] = m
                        stds[i] = sd
                    else:
                        means[i] = (1 - BASELINE_ALPHA) * means[i] + BASELINE_ALPHA * m
                        stds[i] = (1 - BASELINE_ALPHA) * stds[i] + BASELINE_ALPHA * sd

    def calculate_adaptive_risk(density, d_change, inc, outg, d_dev, inc_dev, out_dev, d_std):
        d_anomaly = max(d_dev, 0.0)
        inc_anomaly = max(inc_dev, 0.0)
        growth_anomaly = max(d_change, 0.0) / max(d_std, 1.0)

        d_score = min(d_anomaly / 3.0 * 100.0, 100.0)
        g_score = min(growth_anomaly / 3.0 * 100.0, 100.0)
        i_score = min(inc_anomaly / 3.0 * 100.0, 100.0)

        risk = max(0.0, min(100.0, 0.45 * d_score + 0.25 * g_score + 0.25 * i_score - 0.05 * min(max(out_dev, 0.0) / 3.0 * 100.0, 100.0)))
        strongest = max(d_anomaly, growth_anomaly, inc_anomaly)

        if strongest < 1.0 and risk < 25:
            lvl = "LOW"
        elif strongest < 2.0 and risk < 50:
            lvl = "MEDIUM"
        elif strongest < 3.0 and risk < 75:
            lvl = "HIGH"
        else:
            lvl = "CRITICAL"
        return risk, lvl

    def identify_risk_cause(d_change, inc, outg, d_dev, inc_dev):
        causes = []
        if d_change > 0:
            causes.append("Density increasing")
        if d_change >= 0.8:
            causes.append("Rapid density increase")
        if inc_dev >= 1.0 and inc > outg:
            causes.append("High incoming crowd flow")
        if d_change > 0 and inc > outg:
            causes.append("Sustained crowd build-up")
        if d_dev >= 1.0:
            causes.append("Density above learned baseline")
        return " + ".join(causes) if causes else ("Mild abnormal crowd behaviour" if (d_dev > 0 or inc_dev > 0) else "Normal crowd conditions")

    def select_safe_alternative_zone(target_idx, origin_idx, risk_scores, zone_counts):
        if not (0 <= int(target_idx) < 9):
            return None
        candidates = []
        for i in range(9):
            if i == int(target_idx) or (origin_idx is not None and i == int(origin_idx)):
                continue
            r = float(risk_scores[i])
            d = float(zone_counts[i])
            if r >= 50.0:
                continue
            safety = (100.0 - r) + (100.0 - min(d, 100.0))
            candidates.append((safety, i))
        if not candidates:
            return None
        candidates.sort(reverse=True)
        return f"Z{candidates[0][1] + 1}"

    # Main detection loop for this camera
    while True:
        frame_counter += 1
        ret, frame = cap.read()

        # Continuous non-stop video playback loop
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
            if not ret:
                cap.release()
                cap = cv2.VideoCapture(video_source)
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.05)
                    continue

        height, width = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Camera motion estimation (exception-safe with point check)
        camera_dx, camera_dy = 0, 0
        if prev_gray is not None and frame_counter % CAMERA_MOTION_INTERVAL == 0:
            try:
                prev_pts = cv2.goodFeaturesToTrack(prev_gray, maxCorners=100, qualityLevel=0.02, minDistance=12)
                if prev_pts is not None and len(prev_pts) >= 15:
                    curr_pts, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, gray, prev_pts, None)
                    if curr_pts is not None and status is not None:
                        status_flat = status.ravel()
                        if len(status_flat) == len(prev_pts):
                            old = prev_pts[status_flat == 1]
                            new = curr_pts[status_flat == 1]
                            if len(old) > 10:
                                m = new - old
                                camera_dx = float(np.median(m[:, 0]))
                                camera_dy = float(np.median(m[:, 1]))
            except Exception:
                camera_dx, camera_dy = 0, 0

        camera_offset_x += camera_dx
        camera_offset_y += camera_dy

        zone_width = width // 3
        zone_height = height // 3

        # YOLO Inference (with no_grad context for long-run memory stability)
        with torch.no_grad():
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            class SuppressOpticalFlowFilter:
                def __init__(self, orig_stream):
                    self.orig = orig_stream
                def write(self, s):
                    if "matching points" in s or "GMC failed" in s:
                        return
                    self.orig.write(s)
                def flush(self):
                    self.orig.flush()

            try:
                sys.stdout = SuppressOpticalFlowFilter(old_stdout)
                sys.stderr = SuppressOpticalFlowFilter(old_stderr)
                results = model.track(frame, persist=True, tracker="bytetrack.yaml", classes=[0], imgsz=YOLO_IMGSZ, conf=0.25, verbose=False)
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

        boxes = results[0].boxes

        zone_counts = [0] * 9
        tracked_centroids = []
        active_ids = set()

        is_aerial = ("aerial" in cam_name.lower()) or ("square" in video_source.lower()) or ("pedestrian" in video_source.lower())
        min_conf = 0.25

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

                x1, y1, x2, y2 = xyxy[i]
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2

                zx = int(cx // zone_width)
                zy = int(cy // zone_height)
                zx = min(max(zx, 0), 2)
                zy = min(max(zy, 0), 2)
                zone_idx = zy * 3 + zx

                zone_counts[zone_idx] += 1

                if track_ids is not None and i < len(track_ids):
                    track_id = int(track_ids[i])
                    active_ids.add(track_id)
                    tracked_centroids.append((cx, cy, zone_idx, track_id))

        # Zone flows
        current_incoming = [0] * 9
        current_outgoing = [0] * 9

        for cx, cy, current_zone, track_id in tracked_centroids:
            if track_id in previous_zones:
                prev_z = previous_zones[track_id]
                if prev_z != current_zone:
                    key = (prev_z, current_zone)
                    zone_flows[key] = zone_flows.get(key, 0) + 1
                    current_outgoing[prev_z] += 1
                    current_incoming[current_zone] += 1
            previous_zones[track_id] = current_zone

        # Clean stale tracks
        for tid in list(previous_zones.keys()):
            if tid not in active_ids:
                del previous_zones[tid]

        # Density changes & trends
        density_change = [zone_counts[i] - previous_density[i] for i in range(9)]
        update_adaptive_baseline(zone_counts)
        update_flow_baselines(current_incoming, current_outgoing)

        density_deviations = get_baseline_deviation(zone_counts)
        inc_devs = [ (current_incoming[i] - flow_baseline_mean_in[i]) / max(flow_baseline_std_in[i], 1.0) if flow_baseline_mean_in[i] is not None else 0.0 for i in range(9) ]
        out_devs = [ (current_outgoing[i] - flow_baseline_mean_out[i]) / max(flow_baseline_std_out[i], 1.0) if flow_baseline_mean_out[i] is not None else 0.0 for i in range(9) ]

        for i in range(9):
            buf = density_history_buffer[i]
            buf.append(zone_counts[i])
            if len(buf) >= 5:
                recent_avg = sum(list(buf)[-3:]) / 3.0
                older_avg = sum(list(buf)[:3]) / 3.0
                delta = recent_avg - older_avg
                density_trend_delta[i] = round(delta, 2)
                if delta > TREND_THRESHOLD:
                    density_trends[i] = "RISING"
                elif delta < -TREND_THRESHOLD:
                    density_trends[i] = "FALLING"
                else:
                    density_trends[i] = "STABLE"

        # Adaptive Risk Scores
        risk_scores = []
        risk_levels = []
        risk_causes = []

        for i in range(9):
            r, lvl = calculate_adaptive_risk(
                zone_counts[i],
                density_change[i],
                current_incoming[i],
                current_outgoing[i],
                density_deviations[i],
                inc_devs[i],
                out_devs[i],
                zone_baseline_std[i] if zone_baseline_std[i] is not None else 1.0
            )
            risk_scores.append(r)
            risk_levels.append(lvl)
            risk_causes.append(identify_risk_cause(density_change[i], current_incoming[i], current_outgoing[i], density_deviations[i], inc_devs[i]))

        # Origin detection & Safe alternatives
        potential_origins = []
        prevention_routes = []
        for i in range(9):
            if risk_levels[i] in ("MEDIUM", "HIGH", "CRITICAL"):
                best_origin = None
                max_flow = 0
                for (src, tgt), flow_count in zone_flows.items():
                    if tgt == i and flow_count > max_flow:
                        max_flow = flow_count
                        best_origin = src
                if best_origin is not None:
                    potential_origins.append((best_origin + 1, i + 1, round(risk_scores[i], 1), max_flow))
                    alt = select_safe_alternative_zone(i, best_origin, risk_scores, zone_counts)
                    prevention_routes.append((i, best_origin, alt))

        # Build threat analysis payload
        threats = []
        route_map = {t_idx: {"origin_zone": f"Z{o_idx + 1}", "safe_alternative": alt} for t_idx, o_idx, alt in prevention_routes}

        for i in range(9):
            lvl = risk_levels[i]
            if lvl not in ("MEDIUM", "HIGH", "CRITICAL"):
                continue

            route = route_map.get(i, {})
            origin_zone = route.get("origin_zone")
            safe_alt = route.get("safe_alternative") or "NO ALTERNATIVE YET"

            if lvl == "CRITICAL":
                action = f"IMMEDIATE DIVERSION | Restrict entry to Z{i + 1} | Alert operator | Redirect to {safe_alt}"
            elif lvl == "HIGH":
                action = f"REDIRECT CROWD | Restrict inflow to Z{i + 1} | Move toward {safe_alt}"
            else:
                action = f"PREPARE REDIRECTION | Monitor Z{i + 1} | Prefer {safe_alt} if density rises"

            threats.append({
                "zone": f"Z{i + 1}",
                "density": int(zone_counts[i]),
                "risk_score": round(float(risk_scores[i]), 1),
                "risk_level": lvl,
                "risk_cause": risk_causes[i],
                "possible_origin": origin_zone or "UNKNOWN",
                "safe_alternative": safe_alt,
                "recommended_action": action
            })

        threats.sort(key=lambda item: item["risk_score"], reverse=True)
        highest_lvl = threats[0]["risk_level"] if threats else "LOW"

        prevention_payload = {
            "status": "active",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "threat_detected": len(threats) > 0,
            "highest_risk_zone": threats[0]["zone"] if threats else None,
            "highest_risk_level": highest_lvl,
            "total_people": int(sum(zone_counts)),
            "threat_count": len(threats),
            "threats": threats
        }

        zone_payload = {
            "camera_id": cam_id,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "total_people": int(sum(zone_counts)),
            "zones": [
                {
                    "zone": f"Z{i + 1}",
                    "density": int(zone_counts[i]),
                    "trend": density_trends[i],
                    "trend_delta": density_trend_delta[i],
                    "density_change": int(density_change[i]),
                    "risk_score": round(float(risk_scores[i]), 1),
                    "risk_level": risk_levels[i],
                    "risk_cause": risk_causes[i],
                }
                for i in range(9)
            ]
        }

        # Draw annotations on camera frame
        annotated_frame = frame.copy()
        for row in range(3):
            for col in range(3):
                idx = row * 3 + col
                x1 = col * zone_width
                y1 = row * zone_height
                x2 = (col + 1) * zone_width
                y2 = (row + 1) * zone_height

                lvl = risk_levels[idx]
                color = (34, 197, 94) if lvl == "LOW" else ((234, 179, 8) if lvl == "MEDIUM" else ((249, 115, 22) if lvl == "HIGH" else (239, 68, 68)))
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(annotated_frame, f"Z{idx + 1}: {zone_counts[idx]} ({lvl})", (x1 + 10, y1 + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # Header tag on top of frame
        cv2.rectangle(annotated_frame, (0, 0), (width, 40), (15, 23, 42), -1)
        cv2.putText(annotated_frame, f"CROWDSHIELD LIVE | {cam_name.upper()} | PEOPLE: {sum(zone_counts)}", (15, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Encode JPEG for MJPEG stream
        ret_encode, jpeg_buffer = cv2.imencode(".jpg", annotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        if ret_encode:
            with state_store.lock:
                state_store.jpegs[cam_id] = jpeg_buffer.tobytes()
                state_store.zone_states[cam_id] = zone_payload
                state_store.prevention_states[cam_id] = prevention_payload
                if frame_counter % 10 == 0:
                    state_store.density_history[cam_id].append({
                        "timestamp": zone_payload["timestamp"],
                        "total_people": zone_payload["total_people"],
                        "densities": zone_counts.copy()
                    })
                    state_store.risk_history[cam_id].append({
                        "timestamp": prevention_payload["timestamp"],
                        "highest_risk_level": prevention_payload["highest_risk_level"],
                        "highest_risk_zone": prevention_payload["highest_risk_zone"],
                        "threat_count": prevention_payload["threat_count"],
                        "risk_scores": risk_scores.copy()
                    })

        prev_gray = gray.copy()
        previous_density = zone_counts.copy()
        time.sleep(0.02)

# =====================================================
# MAIN ENTRYPOINT — START ALL DISCOVERED CAMERA WORKERS
# =====================================================

if __name__ == "__main__":
    print("=====================================================")
    print(f" CrowdShield Multi-Camera Server ({len(CAMERAS)} Feeds Discovered)")
    print("=====================================================")

    for cid, cconfig in CAMERAS.items():
        t = threading.Thread(target=run_camera_processor, args=(cid, cconfig["name"], cconfig["source"]), daemon=True)
        t.start()
        print(f" -> [{cid.upper()}] Started thread for: {cconfig['name']} ({cconfig['source']})")

    print(f"\nServer running at: http://{LIVE_API_HOST}:{LIVE_API_PORT}")
    print("Endpoints:")
    print("  - GET /live_prevention.json?cam=cam1")
    print("  - GET /stream?cam=cam1")
    print("  - GET /zones?cam=cam1")
    print("\nPress Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping CrowdShield server.")