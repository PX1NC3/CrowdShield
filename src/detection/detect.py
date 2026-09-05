from ultralytics import YOLO
import cv2
import numpy as np
import csv
import os
import json
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from collections import deque

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", ".."))
_model_path = os.path.join(_PROJECT_ROOT, "models", "yolov8n.pt")
if not os.path.exists(_model_path):
    _model_path = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", "models", "yolov8n.pt"))
if not os.path.exists(_model_path):
    _model_path = "yolov8n.pt"

model = YOLO(_model_path)

video_path = "data/videos/crowd_test.mp4"

cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print("ERROR: Could not open video")
    exit()

# =====================================================
# CAMERA MOTION
# =====================================================

prev_gray = None

camera_offset_x = 0
camera_offset_y = 0

# =====================================================
# TRACKING
# =====================================================

track_history = {}
previous_zones = {}

# Confirmed zone-to-zone flow
zone_flows = {}

# =====================================================
# DENSITY
# =====================================================

previous_density = [0] * 9

# =====================================================
# DENSITY TREND
# =====================================================

TREND_HISTORY_SIZE = 20
TREND_PRINT_INTERVAL = 30
TREND_THRESHOLD = 0.5

density_history_buffer = [
    deque(maxlen=TREND_HISTORY_SIZE)
    for _ in range(9)
]

density_trends = ["STABLE"] * 9
density_trend_delta = [0.0] * 9
last_printed_trend_signature = None
last_origin_signature = None
frame_counter = 0

# =====================================================
# REAL-TIME PERFORMANCE
# =====================================================
# No artificial playback delay. The video window will
# display frames as fast as the analysis pipeline allows.
fps_start_time = datetime.now()
fps_frame_count = 0
processing_fps = 0.0

# =====================================================
# PERFORMANCE TUNING
# =====================================================
# YOLO11n is already the lightweight model. Limiting
# inference resolution is the biggest safe FPS win.
YOLO_IMGSZ = 960

# Camera-motion estimation is expensive. It is only
# needed periodically because zone/tracking analysis
# does not need optical flow on every frame.
CAMERA_MOTION_INTERVAL = 3

# Risk snapshots are stored once every 60 seconds.
RISK_LOG_INTERVAL_SECONDS = 60
last_risk_log_time = None

# =====================================================
# ADAPTIVE BASELINE ENGINE
# =====================================================
# Each zone learns its own normal density from live data.
# No fixed population threshold is used for the baseline.
BASELINE_MIN_SAMPLES = 30
BASELINE_WINDOW_SIZE = 120
BASELINE_ALPHA = 0.05

zone_baseline_mean = [None] * 9
zone_baseline_std = [None] * 9
zone_density_samples = [[] for _ in range(9)]

def update_adaptive_baseline(densities):
    for i in range(9):
        value = float(densities[i])
        samples = zone_density_samples[i]
        samples.append(value)

        if len(samples) > BASELINE_WINDOW_SIZE:
            samples.pop(0)

        if len(samples) >= BASELINE_MIN_SAMPLES:
            mean = sum(samples) / len(samples)
            variance = sum(
                (x - mean) ** 2 for x in samples
            ) / len(samples)
            std = max(variance ** 0.5, 1.0)

            if zone_baseline_mean[i] is None:
                zone_baseline_mean[i] = mean
                zone_baseline_std[i] = std
            else:
                zone_baseline_mean[i] = (
                    (1 - BASELINE_ALPHA)
                    * zone_baseline_mean[i]
                    + BASELINE_ALPHA * mean
                )
                zone_baseline_std[i] = (
                    (1 - BASELINE_ALPHA)
                    * zone_baseline_std[i]
                    + BASELINE_ALPHA * std
                )

def get_baseline_deviation(densities):
    deviations = []

    for i in range(9):
        if zone_baseline_mean[i] is None:
            deviations.append(0.0)
        else:
            deviations.append(
                (
                    float(densities[i])
                    - zone_baseline_mean[i]
                )
                / zone_baseline_std[i]
            )

    return deviations


# =====================================================
# CSV LOGGING
# =====================================================

log_folder = "data/logs"
os.makedirs(log_folder, exist_ok=True)

# =====================================================
# LIVE FRONTEND OUTPUT
# =====================================================
# The frontend can poll this JSON endpoint instead of
# reading CSV files. It always contains the latest
# prevention/threat analysis.
LIVE_PREVENTION_JSON = os.path.join(
    log_folder,
    "live_prevention.json"
)

LIVE_API_HOST = "127.0.0.1"
LIVE_API_PORT = 8765


class LivePreventionHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/live_prevention.json"):
            try:
                with open(LIVE_PREVENTION_JSON, "r", encoding="utf-8") as file:
                    payload = file.read().encode("utf-8")
            except FileNotFoundError:
                payload = json.dumps({
                    "status": "initializing",
                    "threat_detected": False,
                    "threats": []
                }).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
        else:
            self.send_response(404)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

    def log_message(self, format, *args):
        return


def start_live_api():
    server = ThreadingHTTPServer(
        (LIVE_API_HOST, LIVE_API_PORT),
        LivePreventionHandler
    )
    server.daemon_threads = True
    server.serve_forever()


threading.Thread(
    target=start_live_api,
    daemon=True
).start()

print(
    f"Live prevention API: "
    f"http://{LIVE_API_HOST}:{LIVE_API_PORT}/live_prevention.json"
)


csv_path = os.path.join(
    log_folder,
    "density_history.csv"
)

trend_csv_path = os.path.join(
    log_folder,
    "density_trend_history.csv"
)

if not os.path.exists(trend_csv_path):
    with open(trend_csv_path, "w", newline="") as file:
        writer = csv.writer(file)
        header = ["Timestamp"]
        for i in range(1, 10):
            header.append(f"Z{i}_Trend")
        for i in range(1, 10):
            header.append(f"Z{i}_Trend_Delta")
        writer.writerow(header)

risk_csv_path = os.path.join(
    log_folder,
    "risk_history.csv"
)

if not os.path.exists(risk_csv_path):
    with open(risk_csv_path, "w", newline="") as file:
        writer = csv.writer(file)

        header = ["Timestamp"]

        for i in range(1, 10):
            header.extend([
                f"Z{i}_Density",
                f"Z{i}_Trend",
                f"Z{i}_Trend_Delta",
                f"Z{i}_Risk",
                f"Z{i}_Risk_Level",
                f"Z{i}_Baseline",
                f"Z{i}_Baseline_Std",
                f"Z{i}_Baseline_Deviation",
                f"Z{i}_Risk_Cause"
            ])

        writer.writerow(header)


if not os.path.exists(csv_path):

    with open(csv_path, "w", newline="") as file:

        writer = csv.writer(file)

        header = ["Timestamp"]

        for i in range(1, 10):
            header.append(f"Z{i}")

        for i in range(1, 10):
            header.append(f"Z{i}_Change")

        for i in range(1, 10):
            header.append(f"Z{i}_Risk")

        for i in range(1, 10):
            header.append(f"Z{i}_Risk_Level")

        writer.writerow(header)


# =====================================================
# ADAPTIVE RISK ENGINE V2
# =====================================================
# Risk is measured against learned normal behaviour for each zone.
# There is no fixed "X people = HIGH" threshold.

flow_baseline_mean_in = [None] * 9
flow_baseline_std_in = [None] * 9
flow_baseline_mean_out = [None] * 9
flow_baseline_std_out = [None] * 9
flow_samples_in = [[] for _ in range(9)]
flow_samples_out = [[] for _ in range(9)]

FLOW_BASELINE_MIN_SAMPLES = 30
FLOW_BASELINE_WINDOW_SIZE = 120
FLOW_BASELINE_ALPHA = 0.05


def _update_flow_baseline(values, samples_all, means, stds):
    for i in range(9):
        value = float(values[i])
        samples = samples_all[i]
        samples.append(value)

        if len(samples) > FLOW_BASELINE_WINDOW_SIZE:
            samples.pop(0)

        if len(samples) >= FLOW_BASELINE_MIN_SAMPLES:
            mean = sum(samples) / len(samples)
            variance = sum((x - mean) ** 2 for x in samples) / len(samples)
            std = max(variance ** 0.5, 1.0)

            if means[i] is None:
                means[i] = mean
                stds[i] = std
            else:
                means[i] = (1 - FLOW_BASELINE_ALPHA) * means[i] + FLOW_BASELINE_ALPHA * mean
                stds[i] = (1 - FLOW_BASELINE_ALPHA) * stds[i] + FLOW_BASELINE_ALPHA * std


def update_flow_baselines(incoming, outgoing):
    _update_flow_baseline(
        incoming, flow_samples_in, flow_baseline_mean_in, flow_baseline_std_in
    )
    _update_flow_baseline(
        outgoing, flow_samples_out, flow_baseline_mean_out, flow_baseline_std_out
    )


def _z_score(value, mean, std):
    if mean is None or std is None:
        return 0.0
    return (float(value) - mean) / max(std, 1.0)


def calculate_adaptive_risk(
    density,
    density_change,
    incoming,
    outgoing,
    density_deviation,
    incoming_deviation,
    outgoing_deviation,
    density_std
):
    # Positive deviations indicate abnormal crowding/flow.
    density_anomaly = max(density_deviation, 0.0)
    incoming_anomaly = max(incoming_deviation, 0.0)
    outgoing_anomaly = max(outgoing_deviation, 0.0)

    # Growth is normalized using the zone's own learned density variation.
    growth_anomaly = max(density_change, 0.0) / max(density_std, 1.0)

    # Three standard deviations represents the upper end of the anomaly scale.
    density_score = min(density_anomaly / 3.0 * 100.0, 100.0)
    growth_score = min(growth_anomaly / 3.0 * 100.0, 100.0)
    incoming_score = min(incoming_anomaly / 3.0 * 100.0, 100.0)
    outgoing_score = min(outgoing_anomaly / 3.0 * 100.0, 100.0)

    risk = (
        0.45 * density_score
        + 0.25 * growth_score
        + 0.25 * incoming_score
        - 0.05 * outgoing_score
    )

    risk = max(0.0, min(risk, 100.0))

    # Levels are based primarily on statistical abnormality, not headcount.
    strongest_anomaly = max(
        density_anomaly,
        growth_anomaly,
        incoming_anomaly
    )

    if strongest_anomaly < 1.0 and risk < 25:
        level = "LOW"
    elif strongest_anomaly < 2.0 and risk < 50:
        level = "MEDIUM"
    elif strongest_anomaly < 3.0 and risk < 75:
        level = "HIGH"
    else:
        level = "CRITICAL"

    return risk, level


# =====================================================
# PREVENTION ENGINE - STEP 1: RISK CAUSE ANALYSIS
# =====================================================

def identify_risk_cause(
    density,
    density_change,
    incoming,
    outgoing,
    density_deviation,
    incoming_deviation,
):
    causes = []

    # Density is rising relative to the zone's recent behaviour.
    if density_change > 0:
        causes.append("Density increasing")

    # Rapid growth is treated as a stronger warning.
    if density_change >= 0.8:
        causes.append("Rapid density increase")

    # Incoming flow is abnormal relative to the learned flow baseline.
    if incoming_deviation >= 1.0 and incoming > outgoing:
        causes.append("High incoming crowd flow")

    # The zone is receiving more people while also building up.
    if density_change > 0 and incoming > outgoing:
        causes.append("Sustained crowd build-up")

    # Learned density baseline is being exceeded.
    if density_deviation >= 1.0:
        causes.append("Density above learned baseline")

    if not causes:
        if density_deviation > 0 or incoming_deviation > 0:
            return "Mild abnormal crowd behaviour"
        return "Normal crowd conditions"

    return " + ".join(causes)


# =====================================================
# PREVENTION ENGINE - STEP 2: SAFE ALTERNATIVE ZONE
# =====================================================

def select_safe_alternative_zone(target_idx, origin_idx, risk_scores, zone_counts):
    """Return the safest currently available zone.

    target_idx and origin_idx are ZERO-BASED indexes (0..8).
    The function is deliberately defensive so malformed zone
    values can never crash the detection loop.
    """

    if not (0 <= int(target_idx) < 9):
        return None

    if origin_idx is not None and not (0 <= int(origin_idx) < 9):
        return None

    # Make sure both arrays contain all 9 zones.
    if len(risk_scores) != 9 or len(zone_counts) != 9:
        return None

    candidates = []

    for i in range(9):
        if i == int(target_idx) or (
            origin_idx is not None and i == int(origin_idx)
        ):
            continue

        risk = float(risk_scores[i])
        density = float(zone_counts[i])

        # Lower risk + lower density = safer destination.
        safety_score = (
            (100.0 - risk)
            + (100.0 - min(density, 100.0))
        )

        candidates.append(
            (safety_score, i, risk, density)
        )

    if not candidates:
        return None

    candidates.sort(reverse=True)

    return f"Z{candidates[0][1] + 1}"


# =====================================================
# LIVE PREVENTION PAYLOAD
# =====================================================

def write_live_prevention(
    zone_counts,
    risk_scores,
    risk_levels,
    risk_causes,
    potential_origins,
    prevention_routes
):
    """Write the latest threat analysis for the frontend."""

    threats = []

    # Map origin -> target relationships.
    route_map = {}
    for target_idx, origin_idx, alternative in prevention_routes:
        route_map[target_idx] = {
            "origin_zone": f"Z{origin_idx + 1}",
            "safe_alternative": alternative
        }

    # HIGH/CRITICAL zones are always exposed to the frontend.
    # MEDIUM zones are included when an origin/route exists.
    for i in range(9):
        level = risk_levels[i]

        if level not in ("MEDIUM", "HIGH", "CRITICAL"):
            continue

        route = route_map.get(i, {})

        origin_zone = route.get("origin_zone")
        safe_alternative = route.get("safe_alternative")

        # If the origin engine found a source, prefer it.
        if origin_zone is None:
            for source, target, score, flow_count in potential_origins:
                if target == i + 1:
                    origin_zone = f"Z{source}"
                    break

        if safe_alternative is None:
            safe_alternative = "NO ALTERNATIVE YET"

        if level == "CRITICAL":
            action = (
                f"IMMEDIATE DIVERSION | Restrict entry to Z{i + 1} | "
                f"Alert operator | Redirect to {safe_alternative}"
            )
        elif level == "HIGH":
            action = (
                f"REDIRECT CROWD | Restrict inflow to Z{i + 1} | "
                f"Move toward {safe_alternative}"
            )
        else:
            action = (
                f"PREPARE REDIRECTION | Monitor Z{i + 1} | "
                f"Prefer {safe_alternative} if density rises"
            )

        threats.append({
            "zone": f"Z{i + 1}",
            "density": int(zone_counts[i]),
            "risk_score": round(float(risk_scores[i]), 1),
            "risk_level": level,
            "risk_cause": risk_causes[i],
            "possible_origin": origin_zone or "UNKNOWN",
            "safe_alternative": safe_alternative,
            "recommended_action": action
        })

    # Highest risk first.
    threats.sort(
        key=lambda item: item["risk_score"],
        reverse=True
    )

    payload = {
        "status": "active",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "threat_detected": len(threats) > 0,
        "highest_risk_zone": (
            threats[0]["zone"] if threats else None
        ),
        "highest_risk_level": (
            threats[0]["risk_level"] if threats else "LOW"
        ),
        "total_people": int(sum(zone_counts)),
        "threat_count": len(threats),
        "threats": threats
    }

    temp_path = LIVE_PREVENTION_JSON + ".tmp"

    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)

    os.replace(temp_path, LIVE_PREVENTION_JSON)


# =====================================================
# MAIN LOOP
# =====================================================

cv2.namedWindow(
    "CrowdShield - Origin Analysis",
    cv2.WINDOW_NORMAL
)

window_initialized = False

while True:

    frame_counter += 1

    ret, frame = cap.read()

    if not ret:
        break

    height, width = frame.shape[:2]

    gray = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2GRAY
    )

    # =================================================
    # CAMERA MOTION ESTIMATION
    # =================================================

    camera_dx = 0
    camera_dy = 0

    # Optical flow is one of the expensive CPU operations.
    # Estimate camera motion every few frames instead of
    # recalculating it on every frame.
    if (
        prev_gray is not None
        and frame_counter % CAMERA_MOTION_INTERVAL == 0
    ):

        prev_points = cv2.goodFeaturesToTrack(
            prev_gray,
            maxCorners=100,
            qualityLevel=0.02,
            minDistance=12
        )

        if prev_points is not None:

            current_points, status, error = cv2.calcOpticalFlowPyrLK(
                prev_gray,
                gray,
                prev_points,
                None
            )

            if current_points is not None:

                old = prev_points[status == 1]
                new = current_points[status == 1]

                if len(old) > 10:

                    movement = new - old

                    camera_dx = float(
                        np.median(movement[:, 0])
                    )

                    camera_dy = float(
                        np.median(movement[:, 1])
                    )

    camera_offset_x += camera_dx
    camera_offset_y += camera_dy

    # =================================================
    # 3 x 3 ZONES
    # =================================================

    zone_width = width // 3
    zone_height = height // 3

    for i in range(1, 3):

        x = i * zone_width

        cv2.line(
            frame,
            (x, 0),
            (x, height),
            (255, 255, 255),
            2
        )

    for i in range(1, 3):

        y = i * zone_height

        cv2.line(
            frame,
            (0, y),
            (width, y),
            (255, 255, 255),
            2
        )

    zone_number = 1

    for row in range(3):

        for col in range(3):

            x = col * zone_width + 10
            y = row * zone_height + 30

            cv2.putText(
                frame,
                f"Z{zone_number}",
                (x, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2
            )

            zone_number += 1

    # =================================================
    # CURRENT DENSITY
    # =================================================

    zone_counts = [0] * 9

    # Flow during current frame/update
    current_incoming = [0] * 9
    current_outgoing = [0] * 9

    # =================================================
    # YOLO TRACKING
    # =================================================

    results = model.track(
        frame,
        persist=True,
        tracker="bytetrack.yaml",
        classes=[0],
        imgsz=YOLO_IMGSZ,
        conf=0.25,
        verbose=False
    )

    result = results[0]

    people_count = 0

    people_count = 0

    if result.boxes is not None and len(result.boxes) > 0:

        boxes = result.boxes

        classes = (
            boxes.cls
            .int()
            .cpu()
            .tolist()
        ) if boxes.cls is not None else [0] * len(boxes)

        confs = (
            boxes.conf
            .cpu()
            .tolist()
        ) if boxes.conf is not None else [1.0] * len(boxes)

        xyxys = (
            boxes.xyxy
            .cpu()
            .tolist()
        ) if boxes.xyxy is not None else []

        track_ids = (
            boxes.id
            .int()
            .cpu()
            .tolist()
        ) if boxes.id is not None else None

        is_aerial = ("aerial" in video_path.lower()) or ("square" in video_path.lower()) or ("pedestrian" in video_path.lower())
        min_conf = 0.25

        for i in range(len(boxes)):
            if classes[i] != 0:
                continue

            conf = confs[i]
            if conf < min_conf:
                continue

            x1, y1, x2, y2 = map(
                int,
                xyxys[i]
            )

            people_count += 1

            # =============================================
            # PERSON CENTER
            # =============================================

            center_x = int(
                (x1 + x2) / 2
            )

            center_y = int(
                (y1 + y2) / 2
            )

            center = (
                center_x,
                center_y
            )

            # =============================================
            # CURRENT ZONE
            # =============================================

            col = min(
                center_x // zone_width,
                2
            )

            row = min(
                center_y // zone_height,
                2
            )

            zone = row * 3 + col + 1

            zone_counts[zone - 1] += 1

            # =============================================
            # DRAW PERSON
            # =============================================

            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                2
            )

            cv2.circle(
                frame,
                center,
                5,
                (0, 0, 255),
                -1
            )

            # =============================================
            # TRACK-DEPENDENT LOGIC (Only with ByteTrack ID)
            # =============================================

            if track_ids is not None and i < len(track_ids):
                track_id = track_ids[i]

                # =============================================
                # ZONE-TO-ZONE FLOW
                # =============================================

                if track_id in previous_zones:

                    old_zone = previous_zones[
                        track_id
                    ]

                    if old_zone != zone:

                        flow = (
                            old_zone,
                            zone
                        )

                        if flow not in zone_flows:
                            zone_flows[flow] = 0

                        zone_flows[flow] += 1

                        current_incoming[
                            zone - 1
                        ] += 1

                        current_outgoing[
                            old_zone - 1
                        ] += 1

                        print(
                            f"CONFIRMED: ID {track_id}: "
                            f"Z{old_zone} -> Z{zone}"
                        )

                previous_zones[
                    track_id
                ] = zone

                # =============================================
                # MOVEMENT HISTORY
                # =============================================

                if track_id not in track_history:

                    track_history[
                        track_id
                    ] = []

                corrected_x = int(
                    center_x - camera_offset_x
                )

                corrected_y = int(
                    center_y - camera_offset_y
                )

                track_history[
                    track_id
                ].append(
                    (
                        corrected_x,
                        corrected_y
                    )
                )

                if len(
                    track_history[track_id]
                ) > 30:

                    track_history[
                        track_id
                    ].pop(0)

                cv2.putText(
                    frame,
                    f"ID {track_id} | Z{zone}",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

                # =============================================
                # MOVEMENT TRAIL
                # =============================================

                points = track_history[
                    track_id
                ]

                display_points = []

                for px, py in points:

                    display_x = int(
                        px + camera_offset_x
                    )

                    display_y = int(
                        py + camera_offset_y
                    )

                    display_points.append(
                        (
                            display_x,
                            display_y
                        )
                    )

                for idx in range(
                    1,
                    len(display_points)
                ):

                    cv2.line(
                        frame,
                        display_points[idx - 1],
                        display_points[idx],
                        (255, 0, 0),
                        2
                    )
            else:
                cv2.putText(
                    frame,
                    f"Z{zone}",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

    # =================================================
    # DENSITY CHANGE
    # =================================================

    density_change = []

    for i in range(9):

        change = (
            zone_counts[i]
            - previous_density[i]
        )

        density_change.append(
            change
        )

    # =================================================
    # DENSITY TREND
    # =================================================

    for i in range(9):
        density_history_buffer[i].append(zone_counts[i])

        if len(density_history_buffer[i]) >= 6:
            history = list(density_history_buffer[i])
            midpoint = len(history) // 2

            first_avg = sum(history[:midpoint]) / midpoint
            second_half = history[midpoint:]
            second_avg = sum(second_half) / len(second_half)

            delta = second_avg - first_avg
            density_trend_delta[i] = delta

            if delta > TREND_THRESHOLD:
                density_trends[i] = "RISING"
            elif delta < -TREND_THRESHOLD:
                density_trends[i] = "FALLING"
            else:
                density_trends[i] = "STABLE"
        else:
            density_trends[i] = "STABLE"
            density_trend_delta[i] = 0.0

    # Print only when the trend pattern changes.
    if frame_counter % TREND_PRINT_INTERVAL == 0:
        trend_signature = tuple(density_trends)

        if trend_signature != last_printed_trend_signature:
            print("\n--- DENSITY TREND ---")
            for i in range(9):
                print(
                    f"Z{i + 1}: {density_trends[i]:7} "
                    f"{density_trend_delta[i]:+.1f}"
                )
            last_printed_trend_signature = trend_signature

        # Keep trend data separate from the existing density CSV.
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        trend_row = [timestamp]
        trend_row.extend(density_trends)
        trend_row.extend(round(x, 2) for x in density_trend_delta)

        with open(trend_csv_path, "a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(trend_row)

    # =================================================
    # ADAPTIVE BASELINE UPDATE
    # =================================================

    update_adaptive_baseline(zone_counts)

    baseline_deviation = get_baseline_deviation(
        zone_counts
    )

    # =================================================
    # ADAPTIVE FLOW BASELINES + RISK CALCULATION
    # =================================================

    update_flow_baselines(
        current_incoming,
        current_outgoing
    )

    risk_scores = []
    risk_levels = []

    for i in range(9):

        incoming_deviation = _z_score(
            current_incoming[i],
            flow_baseline_mean_in[i],
            flow_baseline_std_in[i]
        )

        outgoing_deviation = _z_score(
            current_outgoing[i],
            flow_baseline_mean_out[i],
            flow_baseline_std_out[i]
        )

        density_std = (
            zone_baseline_std[i]
            if zone_baseline_std[i] is not None
            else 1.0
        )

        risk, level = calculate_adaptive_risk(
            zone_counts[i],
            density_change[i],
            current_incoming[i],
            current_outgoing[i],
            baseline_deviation[i],
            incoming_deviation,
            outgoing_deviation,
            density_std
        )

        risk_scores.append(risk)
        risk_levels.append(level)

    # =================================================
    # PREVENTION ENGINE - STEP 1: CAUSE ANALYSIS
    # =================================================

    risk_causes = []

    for i in range(9):
        cause = identify_risk_cause(
            zone_counts[i],
            density_change[i],
            current_incoming[i],
            current_outgoing[i],
            baseline_deviation[i],
            _z_score(
                current_incoming[i],
                flow_baseline_mean_in[i],
                flow_baseline_std_in[i]
            ),
        )

        risk_causes.append(cause)

    # Print only zones where a meaningful risk cause exists.
    if frame_counter % TREND_PRINT_INTERVAL == 0:
        print("\n--- PREVENTION / RISK CAUSE ANALYSIS ---")

        for i in range(9):
            if risk_levels[i] != "LOW" or risk_causes[i] != "Normal crowd conditions":
                print(
                    f"Z{i + 1}: {risk_levels[i]} "
                    f"{risk_scores[i]:.1f} | "
                    f"Cause: {risk_causes[i]}"
                )

    # =================================================
    # CROWD BUILD-UP DETECTION
    # =================================================

    # Find zones where crowd is actually increasing
    build_up_zones = []

    for i in range(9):

        if (
            density_change[i] > 0
            and zone_counts[i] >= 3
        ):

            build_up_zones.append(i)

    # =================================================
    # POTENTIAL ORIGIN DETECTION
    # =================================================

    potential_origins = []

    for target_zone in build_up_zones:

        target_index = target_zone

        # We look for zones that have previously
        # sent people into the build-up zone.

        source_scores = []

        for source_zone in range(9):

            if source_zone == target_index:
                continue

            flow_count = zone_flows.get(
                (
                    source_zone + 1,
                    target_index + 1
                ),
                0
            )

            if flow_count <= 0:
                continue

            # Source contribution score
            flow_score = min(
                flow_count / 10 * 100,
                100
            )

            # Source should not itself be heavily
            # building up at the same time.
            source_growth = max(
                density_change[source_zone],
                0
            )

            # Higher flow into target = stronger source
            # Lower source density growth = stronger source
            origin_score = (
                0.75 * flow_score
                + 0.25 * (
                    100
                    - min(
                        source_growth / 5 * 100,
                        100
                    )
                )
            )

            source_scores.append(
                (
                    source_zone + 1,
                    target_index + 1,
                    origin_score,
                    flow_count
                )
            )

        if source_scores:

            source_scores.sort(
                key=lambda x: x[2],
                reverse=True
            )

            best_source = source_scores[0]

            potential_origins.append(
                (
                    best_source[0],
                    best_source[1],
                    best_source[2],
                    best_source[3]
                )
            )

    # =================================================
    # PREVENTION ENGINE - STEP 2
    # SAFE ALTERNATIVE + FRONTEND OUTPUT
    # =================================================

    prevention_routes = []

    if potential_origins:
        for origin_zone, target_zone, origin_score, flow_count in potential_origins:

            try:
                origin_idx = int(origin_zone) - 1
                target_idx = int(target_zone) - 1
            except (TypeError, ValueError):
                continue

            if not (0 <= origin_idx < 9):
                continue

            if not (0 <= target_idx < 9):
                continue

            if len(risk_levels) != 9 or len(risk_scores) != 9:
                continue

            alternative = select_safe_alternative_zone(
                target_idx,
                origin_idx,
                risk_scores,
                zone_counts
            )

            if alternative is not None:
                prevention_routes.append(
                    (target_idx, origin_idx, alternative)
                )

    # Write a fresh live JSON snapshot every analysis frame.
    # The frontend can poll this without touching CSV logs.
    write_live_prevention(
        zone_counts,
        risk_scores,
        risk_levels,
        risk_causes,
        potential_origins,
        prevention_routes
    )

    # Terminal output remains useful for debugging/demo.
    if prevention_routes and frame_counter % TREND_PRINT_INTERVAL == 0:
        print("\n--- PREVENTION / FRONTEND ACTIONS ---")

        for target_idx, origin_idx, alternative in prevention_routes:
            risk_level = risk_levels[target_idx]

            if risk_level in ("MEDIUM", "HIGH", "CRITICAL"):
                if risk_level == "CRITICAL":
                    action = (
                        f"IMMEDIATE DIVERSION + RESTRICT ENTRY + "
                        f"ALERT OPERATOR -> {alternative}"
                    )
                elif risk_level == "HIGH":
                    action = (
                        f"REDIRECT CROWD + RESTRICT INFLOW -> "
                        f"{alternative}"
                    )
                else:
                    action = (
                        f"PREPARE REDIRECTION -> {alternative}"
                    )

                print(
                    f"Threat Zone: Z{target_idx + 1} | "
                    f"Density: {zone_counts[target_idx]} | "
                    f"Risk: {risk_level} "
                    f"{risk_scores[target_idx]:.1f} | "
                    f"Origin: Z{origin_idx + 1} | "
                    f"Safe Alternative: {alternative} | "
                    f"Action: {action}"
                )

    # =================================================
    # TERMINAL ORIGIN OUTPUT
    # =================================================

    if potential_origins:

        origin_signature = tuple(
            (source, target)
            for source, target, score, flow_count
            in potential_origins
        )

        if (
            frame_counter % TREND_PRINT_INTERVAL == 0
            and origin_signature != last_origin_signature
        ):
            print("\n--- CROWD ORIGIN ANALYSIS ---")

            for (
                source,
                target,
                score,
                flow_count
            ) in potential_origins:

                print(
                    f"Potential Origin: Z{source} "
                    f"-> Build-up Zone: Z{target} | "
                    f"Origin Score: {score:.1f} | "
                    f"Flow: {flow_count}"
                )

            last_origin_signature = origin_signature

    # =================================================
    # CSV LOGGING
    # =================================================

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    row = [timestamp]

    row.extend(zone_counts)

    row.extend(density_change)

    row.extend(
        [
            round(score, 2)
            for score in risk_scores
        ]
    )

    row.extend(risk_levels)

    with open(
        csv_path,
        "a",
        newline=""
    ) as file:

        writer = csv.writer(file)

        writer.writerow(row)

    # =================================================
    # DISPLAY DENSITY
    # =================================================

    for i in range(9):

        row_index = i // 3
        col_index = i % 3

        x = (
            col_index * zone_width
            + 10
        )

        y = (
            (row_index + 1)
            * zone_height
            - 15
        )

        cv2.putText(
            frame,
            f"People: {zone_counts[i]}",
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2
        )

    # =================================================
    # DISPLAY RISK
    # =================================================

    risk_y = 110

    for i in range(9):

        text = (
            f"Z{i + 1}: "
            f"{risk_levels[i]} "
            f"{risk_scores[i]:.0f}"
        )

        cv2.putText(
            frame,
            text,
            (30, risk_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 0, 255),
            2
        )

        risk_y += 23

    # =================================================
    # DISPLAY DENSITY TREND
    # =================================================

    trend_y = 540

    for i in range(9):
        row_index = i // 3
        col_index = i % 3

        x = col_index * zone_width + 10
        y = trend_y + row_index * 22

        cv2.putText(
            frame,
            f"Z{i + 1}: {density_trends[i]}",
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 255, 255),
            1
        )

    # =================================================
    # DISPLAY POTENTIAL ORIGIN
    # =================================================

    origin_y = 330

    for (
        source,
        target,
        score,
        flow_count
    ) in potential_origins[:3]:

        text = (
            f"Origin: Z{source} -> Z{target} "
            f"({score:.0f})"
        )

        cv2.putText(
            frame,
            text,
            (30, origin_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 165, 255),
            2
        )

        origin_y += 23

    # =================================================
    # TOTAL PEOPLE
    # =================================================

    cv2.putText(
        frame,
        f"Total People: {people_count}",
        (30, height - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 0, 255),
        2
    )

    # =================================================
    # CAMERA MOTION
    # =================================================

    cv2.putText(
        frame,
        f"Camera: X {camera_dx:.1f} "
        f"Y {camera_dy:.1f}",
        (30, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 0),
        2
    )

    # =================================================
    # REAL-TIME FPS
    # =================================================

    fps_frame_count += 1
    fps_elapsed = (
        datetime.now() - fps_start_time
    ).total_seconds()

    if fps_elapsed >= 1.0:
        processing_fps = (
            fps_frame_count / fps_elapsed
        )

        fps_frame_count = 0
        fps_start_time = datetime.now()

    # =================================================
    # RISK HISTORY CSV
    # =================================================
    # Store one complete 9-zone snapshot every
    # RISK_LOG_INTERVAL_SECONDS. This is independent
    # of video playback speed.

    current_time = datetime.now()

    if (
        last_risk_log_time is None
        or (
            current_time - last_risk_log_time
        ).total_seconds() >= RISK_LOG_INTERVAL_SECONDS
    ):

        timestamp = current_time.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        risk_row = [timestamp]

        for i in range(9):
            risk_row.extend([
                zone_counts[i],
                density_trends[i],
                round(
                    density_trend_delta[i],
                    2
                ),
                round(
                    risk_scores[i],
                    2
                ),
                risk_levels[i],
                round(
                    zone_baseline_mean[i]
                    if zone_baseline_mean[i] is not None
                    else 0.0,
                    2
                ),
                round(
                    zone_baseline_std[i]
                    if zone_baseline_std[i] is not None
                    else 0.0,
                    2
                ),
                round(
                    baseline_deviation[i],
                    2
                ),
                risk_causes[i]
            ])

        with open(
            risk_csv_path,
            "a",
            newline=""
        ) as file:

            writer = csv.writer(file)
            writer.writerow(risk_row)

        last_risk_log_time = current_time

    # =================================================
    # SHOW FRAME
    # =================================================

    # =================================================
    # SCREEN-FIT DISPLAY
    # =================================================
    # Keep the complete 3x3 zone frame visible on screen.
    # Analysis/detection still runs on the original frame;
    # only the copy used for display is resized.
    max_display_w = 1280
    max_display_h = 680

    display_scale = min(
        max_display_w / width,
        max_display_h / height,
        1.0
    )

    display_frame = cv2.resize(
        frame,
        (
            int(width * display_scale),
            int(height * display_scale)
        ),
        interpolation=cv2.INTER_AREA
    )

    if not window_initialized:
        cv2.resizeWindow(
            "CrowdShield - Origin Analysis",
            display_frame.shape[1],
            display_frame.shape[0]
        )
        window_initialized = True

    learned_zones = sum(
        1 for value in zone_baseline_mean
        if value is not None
    )

    cv2.putText(
        display_frame,
        f"Adaptive Baseline: {learned_zones}/9",
        (20, 65),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2
    )

    cv2.putText(
        display_frame,
        f"Processing FPS: {processing_fps:.1f}",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2
    )

    cv2.imshow(
        "CrowdShield - Origin Analysis",
        display_frame
    )

    # 1 ms wait only for OpenCV event handling / Q key.
    # There is no artificial playback delay here.
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

    prev_gray = gray.copy()

    previous_density = zone_counts.copy()


# =====================================================
# CLEANUP
# =====================================================

cap.release()

cv2.destroyAllWindows()

print("\nCrowdShield analysis completed.")
print(f"Density data saved to: {csv_path}")
print(f"Density trend data saved to: {trend_csv_path}")
print(f"Risk history saved to: {risk_csv_path}")
print(f"Live prevention data: http://{LIVE_API_HOST}:{LIVE_API_PORT}/live_prevention.json")