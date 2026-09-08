"""
CrowdShield — Synthetic Demo Simulation Engine
================================================
Generates realistic, time-evolving synthetic data for:
1. Multi-camera feeds (3x3 zones, density, trends, flow, risk scores/levels, causes, origin, safe alternatives, prevention actions, annotated frame rendering)
2. Geographic Heatmap cells (lat/lon, density, trends, risk levels, threat zones, prevention recommendations)

Supported Scenarios:
- "normal": Low density, stable/flowing crowd, normal conditions across all zones & cells.
- "buildup": Growing crowd density in focal zones/cells, rising trends, medium risk emerging.
- "critical": High/Critical crowd crush in focal zones (e.g. Z5 / central cells), severe bottlenecks, emergency diversion actions.
- "dispersal": Rapid crowd movement away from focal zones into safe alternatives, falling trends, crowd clearing.

Time evolution:
- Uses sinusoidal/smooth progression based on elapsed time so numbers subtly fluctuate and evolve naturally without jumping erratically.
"""

from __future__ import annotations

import math
import time
import cv2
import numpy as np
from datetime import datetime, timezone
from typing import Literal

ScenarioType = Literal["normal", "buildup", "critical", "dispersal"]

SCENARIOS = ["normal", "buildup", "critical", "dispersal"]


class DemoDataGenerator:
    """Singleton simulation generator maintaining demo scenario state and time progression."""

    def __init__(self):
        self.scenario: ScenarioType = "buildup"
        self.start_time: float = time.time()
        self.camera_enabled: bool = False
        self.heatmap_enabled: bool = False

    def set_scenario(self, scenario: str) -> str:
        s = scenario.lower().strip()
        if s in SCENARIOS:
            self.scenario = s  # type: ignore
            self.start_time = time.time()
            return self.scenario
        return self.scenario

    def toggle_camera(self, enable: bool | None = None) -> bool:
        if enable is None:
            self.camera_enabled = not self.camera_enabled
        else:
            self.camera_enabled = bool(enable)
        return self.camera_enabled

    def toggle_heatmap(self, enable: bool | None = None) -> bool:
        if enable is None:
            self.heatmap_enabled = not self.heatmap_enabled
        else:
            self.heatmap_enabled = bool(enable)
        return self.heatmap_enabled

    def _get_time_phase(self) -> float:
        """Returns elapsed time in seconds with periodic phase."""
        elapsed = time.time() - self.start_time
        return elapsed

    # =========================================================================
    # CAMERA SYNTHETIC DATA GENERATION
    # =========================================================================

    def generate_camera_data(self, cam_id: str = "cam1", user_role: str = "manager") -> dict:
        """
        Generates full camera payload matching detect.py output.
        user_role: 'manager' gets full risk/origin/prevention diagnostics.
                   'user' gets safe public guidance only.
        """
        t = self._get_time_phase()
        osc = math.sin(t * 0.4)
        osc_fast = math.sin(t * 1.2)

        # Baseline per scenario
        if self.scenario == "normal":
            # Normal crowd: low density, uniform distribution
            base_counts = [4, 5, 3, 6, 8, 5, 3, 4, 4]
            fluct = [int(round(osc * 1.5 + (i % 2) * osc_fast)) for i in range(9)]
            zone_counts = [max(1, base_counts[i] + fluct[i]) for i in range(9)]
            trends = ["STABLE"] * 9
            trend_deltas = [0.1 * math.sin(t + i) for i in range(9)]
            risk_scores = [round(max(5.0, min(22.0 + 3.0 * osc, 30.0)), 1) for _ in range(9)]
            risk_levels = ["LOW"] * 9
            risk_causes = ["Normal crowd conditions"] * 9
            prevention_routes = []
            focal_zone = None

        elif self.scenario == "buildup":
            # Crowd build-up: Gathering rapidly in Z4, Z5, Z6
            base_counts = [6, 8, 5, 18, 26, 19, 7, 10, 8]
            scale = 1.0 + 0.25 * math.sin(t * 0.2)
            zone_counts = [
                max(2, int(round(base_counts[i] * scale + (2 if i in (3, 4, 5) else 0) * osc_fast)))
                for i in range(9)
            ]
            trends = ["STABLE", "STABLE", "STABLE", "RISING", "RISING", "RISING", "STABLE", "RISING", "STABLE"]
            trend_deltas = [0.2, 0.3, 0.1, 1.4, 2.2, 1.6, 0.3, 0.8, 0.2]
            risk_scores = [
                18.0, 24.0, 15.0,
                58.0 + 5.0 * osc, 68.0 + 6.0 * osc, 61.0 + 4.0 * osc,
                22.0, 36.0, 20.0
            ]
            risk_scores = [round(max(5.0, min(s, 95.0)), 1) for s in risk_scores]
            risk_levels = [
                "LOW", "LOW", "LOW",
                "HIGH" if risk_scores[3] >= 60 else "MEDIUM",
                "HIGH" if risk_scores[4] >= 60 else "MEDIUM",
                "HIGH" if risk_scores[5] >= 60 else "MEDIUM",
                "LOW", "MEDIUM", "LOW"
            ]
            risk_causes = [
                "Normal crowd conditions", "Normal crowd conditions", "Normal crowd conditions",
                "Density increasing + Inflow from Z1",
                "Sustained crowd build-up + Rapid density increase",
                "Density increasing + Inflow from Z3",
                "Normal crowd conditions", "Mild abnormal crowd behaviour", "Normal crowd conditions"
            ]
            prevention_routes = [(4, 1, "Z2"), (3, 0, "Z7"), (5, 2, "Z9")]
            focal_zone = "Z5"

        elif self.scenario == "critical":
            # High / Critical Risk: Severe bottleneck in Z5 & Z2, danger of surge
            base_counts = [12, 38, 14, 28, 54, 32, 10, 16, 11]
            surge = 1.0 + 0.15 * math.sin(t * 0.3)
            zone_counts = [
                max(4, int(round(base_counts[i] * surge + (3 if i in (1, 4) else 1) * osc_fast)))
                for i in range(9)
            ]
            trends = ["RISING", "RISING", "RISING", "RISING", "RISING", "RISING", "STABLE", "STABLE", "STABLE"]
            trend_deltas = [0.8, 2.8, 0.9, 1.8, 3.7, 2.1, 0.4, 0.5, 0.3]
            risk_scores = [
                38.0, 84.0 + 4.0 * osc, 42.0,
                72.0 + 3.0 * osc, 94.0 + 3.0 * osc, 76.0 + 4.0 * osc,
                26.0, 34.0, 28.0
            ]
            risk_scores = [round(max(10.0, min(s, 99.0)), 1) for s in risk_scores]
            risk_levels = [
                "MEDIUM", "CRITICAL", "MEDIUM",
                "HIGH", "CRITICAL", "HIGH",
                "LOW", "MEDIUM", "LOW"
            ]
            risk_causes = [
                "Inflow toward bottleneck",
                "Critical density anomaly + High incoming surge",
                "Inflow toward bottleneck",
                "Severe bottleneck + Rapid density increase",
                "Extreme density spike + Zero outflow bottleneck",
                "Severe bottleneck + Inflow from perimeter",
                "Normal conditions", "Perimeter monitoring", "Normal conditions"
            ]
            prevention_routes = [(4, 1, "Z8"), (1, 0, "Z3"), (3, 0, "Z7"), (5, 2, "Z9")]
            focal_zone = "Z5"

        else:  # dispersal
            # Crowd Dispersal: Clearing out, moving from center to outer zones
            base_counts = [10, 8, 12, 11, 14, 12, 14, 11, 15]
            fade = max(0.5, 1.0 - 0.05 * (t % 30))
            zone_counts = [
                max(2, int(round(base_counts[i] * fade + osc_fast)))
                for i in range(9)
            ]
            trends = ["FALLING", "FALLING", "FALLING", "FALLING", "FALLING", "FALLING", "STABLE", "FALLING", "STABLE"]
            trend_deltas = [-1.2, -1.8, -0.9, -1.4, -2.5, -1.6, 0.1, -0.8, 0.2]
            risk_scores = [
                22.0, 28.0, 24.0,
                32.0, 38.0, 34.0,
                20.0, 22.0, 18.0
            ]
            risk_scores = [round(max(5.0, min(s, 60.0)), 1) for s in risk_scores]
            risk_levels = [
                "LOW", "MEDIUM", "LOW",
                "MEDIUM", "MEDIUM", "MEDIUM",
                "LOW", "LOW", "LOW"
            ]
            risk_causes = ["Active crowd dispersal in progress"] * 9
            prevention_routes = [(4, 1, "Z7")]
            focal_zone = "Z5"

        # Build threats / areas list
        threats = []
        route_map = {t_idx: {"origin_zone": f"Z{o_idx + 1}", "safe_alternative": alt} for t_idx, o_idx, alt in prevention_routes}

        for i in range(9):
            lvl = risk_levels[i]
            if lvl not in ("MEDIUM", "HIGH", "CRITICAL"):
                continue

            route = route_map.get(i, {})
            origin_zone = route.get("origin_zone", "Z1")
            safe_alt = route.get("safe_alternative", "Z7")

            # Simple crowd status for public users
            if lvl == "CRITICAL":
                crowd_status = "Crowded"
                action = f"IMMEDIATE DIVERSION | Restrict entry to Z{i + 1} | Alert operator | Redirect to {safe_alt}"
                user_action = f"High foot-traffic in Zone {i + 1}. Recommended alternate path: Zone {safe_alt}."
                safety_instruction = f"Proceed calmly. Follow signage toward Zone {safe_alt}."
            elif lvl == "HIGH":
                crowd_status = "Moderate"
                action = f"REDIRECT CROWD | Restrict inflow to Z{i + 1} | Move toward {safe_alt}"
                user_action = f"Moderate movement in Zone {i + 1}. Less-crowded route available via Zone {safe_alt}."
                safety_instruction = f"Keep walking with the flow toward Zone {safe_alt}."
            else:
                crowd_status = "Low"
                action = f"PREPARE REDIRECTION | Monitor Z{i + 1} | Prefer {safe_alt} if density rises"
                user_action = f"Normal movement in Zone {i + 1}. Open path at Zone {safe_alt}."
                safety_instruction = "Maintain regular pace. Clear pathways available."

            if user_role == "manager":
                threat_item = {
                    "zone": f"Z{i + 1}",
                    "density": int(zone_counts[i]),
                    "risk_score": float(risk_scores[i]),
                    "risk_level": lvl,
                    "risk_cause": risk_causes[i],
                    "possible_origin": origin_zone,
                    "safe_alternative": safe_alt,
                    "recommended_action": action,
                }
            else:
                # Public user safe sanitized representation - NO risk scores, NO origins, NO internal causes, NO HIGH/CRITICAL labels
                threat_item = {
                    "zone": f"Z{i + 1}",
                    "crowd_status": crowd_status,
                    "safe_alternative": safe_alt,
                    "recommended_route": f"Use Zone {safe_alt} for less congestion",
                    "safe_guidance": user_action,
                    "safety_instruction": safety_instruction,
                    "recommended_action": user_action,
                }

            threats.append(threat_item)

        if user_role == "manager":
            threats.sort(key=lambda item: item["risk_score"], reverse=True)
            highest_lvl = threats[0]["risk_level"] if threats else "LOW"
        else:
            # Order public guidance with busy zones first
            severity_order = {"Crowded": 3, "Moderate": 2, "Low": 1}
            threats.sort(key=lambda item: severity_order.get(item.get("crowd_status"), 0), reverse=True)
            highest_lvl = "Crowded" if any(t.get("crowd_status") == "Crowded" for t in threats) else ("Moderate" if any(t.get("crowd_status") == "Moderate" for t in threats) else "Low")

        total_people = int(sum(zone_counts))

        # Camera summary meta for multi-camera switcher (CAM 1 and CAM 2 match data/videos)
        if user_role == "manager":
            cameras_summary = {
                "cam1": {
                    "name": "CAM 1 - Crowd Test",
                    "risk_level": highest_lvl if cam_id == "cam1" else "LOW",
                    "threat_count": len(threats) if cam_id == "cam1" else 0,
                    "total_people": total_people if cam_id == "cam1" else int(total_people * 0.5),
                    "has_serious_threat": (highest_lvl in ("HIGH", "CRITICAL")) if cam_id == "cam1" else False,
                },
                "cam2": {
                    "name": "CAM 2 - Busy Pedestrian Street",
                    "risk_level": highest_lvl if cam_id == "cam2" else ("LOW" if self.scenario != "critical" else "MEDIUM"),
                    "threat_count": len(threats) if cam_id == "cam2" else (0 if self.scenario != "critical" else 1),
                    "total_people": total_people if cam_id == "cam2" else int(total_people * 0.4),
                    "has_serious_threat": (highest_lvl in ("HIGH", "CRITICAL")) if cam_id == "cam2" else False,
                },
            }
        else:
            # Public camera summary
            cameras_summary = {
                "cam1": {
                    "name": "CAM 1 - Crowd Test",
                    "crowd_status": highest_lvl if cam_id == "cam1" else "Low",
                    "notice": "Active monitoring",
                },
                "cam2": {
                    "name": "CAM 2 - Busy Pedestrian Street",
                    "crowd_status": highest_lvl if cam_id == "cam2" else "Low",
                    "notice": "Clear routes available",
                },
            }

        # Prevention / Public Guidance payload
        if user_role == "manager":
            prevention_payload = {
                "status": "active",
                "demo_mode": True,
                "demo_scenario": self.scenario,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                "active_camera": cam_id,
                "threat_detected": len(threats) > 0,
                "highest_risk_zone": threats[0]["zone"] if threats else None,
                "highest_risk_level": highest_lvl,
                "total_people": total_people,
                "threat_count": len(threats),
                "cameras": cameras_summary,
                "threats": threats,
                "all_threats": threats,
            }

            zone_payload = {
                "camera_id": cam_id,
                "demo_mode": True,
                "demo_scenario": self.scenario,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                "total_people": total_people,
                "zones": [
                    {
                        "zone": f"Z{i + 1}",
                        "density": int(zone_counts[i]),
                        "trend": trends[i],
                        "trend_delta": round(float(trend_deltas[i]), 2),
                        "density_change": int(round(trend_deltas[i] * 2)),
                        "risk_score": float(risk_scores[i]),
                        "risk_level": risk_levels[i],
                        "risk_cause": risk_causes[i],
                    }
                    for i in range(9)
                ],
            }
        else:
            # Strictly sanitized Public User guidance payload
            public_zones = []
            for i in range(9):
                lvl = risk_levels[i]
                c_status = "Crowded" if lvl in ("HIGH", "CRITICAL") else ("Moderate" if lvl == "MEDIUM" else "Low")
                public_zones.append({
                    "zone": f"Z{i + 1}",
                    "crowd_status": c_status,
                    "nav_recommendation": f"Clear walking path" if c_status == "Low" else (f"Moderate foot traffic" if c_status == "Moderate" else "High activity — prefer alternate routes"),
                    "safer_alternative": route_map.get(i, {}).get("safe_alternative", "Z7") if c_status == "Crowded" else None,
                })

            prevention_payload = {
                "status": "active",
                "role": "user",
                "demo_mode": True,
                "demo_scenario": self.scenario,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                "active_camera": cam_id,
                "overall_crowd_status": highest_lvl,
                "guidance_notices": threats,
                "cameras": cameras_summary,
                "threats": threats,  # backwards compatible array name for UI components
                "public_safety_message": "All walkways are actively monitored for your safety. Follow navigation guides for the smoothest route.",
            }

            zone_payload = {
                "camera_id": cam_id,
                "role": "user",
                "demo_mode": True,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                "zones": public_zones,
            }

        return {
            "prevention": prevention_payload,
            "zones": zone_payload,
            "zone_counts": zone_counts,
            "risk_levels": risk_levels,
        }

    # =========================================================================
    # SYNTHETIC CAMERA FRAME RENDERER (MJPEG stream in Demo Mode)
    # =========================================================================

    def generate_demo_frame(self, cam_id: str = "cam1") -> bytes:
        """Renders an animated synthetic 3x3 camera frame with live crowd dots and HUD."""
        t = self._get_time_phase()
        cam_data = self.generate_camera_data(cam_id)
        zone_counts = cam_data["zone_counts"]
        risk_levels = cam_data["risk_levels"]

        width, height = 640, 360
        # Dark stadium / concourse background texture
        frame = np.full((height, width, 3), (20, 24, 33), dtype=np.uint8)

        # Subtle grid background pattern
        for y in range(0, height, 20):
            cv2.line(frame, (0, y), (width, y), (28, 33, 44), 1)
        for x in range(0, width, 20):
            cv2.line(frame, (x, 0), (x, height), (28, 33, 44), 1)

        zone_w = width // 3
        zone_h = height // 3

        # Render simulated people dots inside each zone
        np.random.seed(42)  # stable positions that oscillate
        for z_idx in range(9):
            row = z_idx // 3
            col = z_idx % 3
            zx1 = col * zone_w
            zy1 = row * zone_h
            count = zone_counts[z_idx]
            lvl = risk_levels[z_idx]

            # Zone color
            color = (
                (34, 197, 94) if lvl == "LOW" else
                (234, 179, 8) if lvl == "MEDIUM" else
                (249, 115, 22) if lvl == "HIGH" else
                (239, 68, 68)
            )

            # Draw simulated walking bounding boxes / dots
            for p in range(min(count, 35)):
                bx = int(zx1 + 20 + (p * 47 + int(math.sin(t * 1.5 + p + z_idx) * 12)) % (zone_w - 40))
                by = int(zy1 + 35 + (p * 31 + int(math.cos(t * 1.2 + p + z_idx) * 10)) % (zone_h - 50))
                # Bounding box
                cv2.rectangle(frame, (bx - 6, by - 12), (bx + 6, by + 12), (90, 130, 255), 1)
                # Head dot
                cv2.circle(frame, (bx, by - 8), 3, (220, 220, 255), -1)

            # Zone boundary box
            cv2.rectangle(frame, (zx1, zy1), (zx1 + zone_w, zy1 + zone_h), color, 2)
            # Label
            cv2.putText(
                frame,
                f"Z{z_idx + 1}: {count} ({lvl})",
                (zx1 + 8, zy1 + 22),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
            )

        # Header Bar
        cv2.rectangle(frame, (0, 0), (width, 36), (15, 23, 42), -1)
        cv2.putText(
            frame,
            f"DEMO MODE | {cam_id.upper()} | SCENARIO: {self.scenario.upper()} | PEOPLE: {sum(zone_counts)}",
            (12, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (240, 240, 255),
            2,
        )

        # Demo Mode Badge in Top-Right
        cv2.rectangle(frame, (width - 110, 6), (width - 10, 30), (79, 70, 229), -1)
        cv2.putText(
            frame,
            "DEMO ACTIVE",
            (width - 102, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (255, 255, 255),
            1,
        )

        ret, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        return jpeg.tobytes() if ret else b""

    # =========================================================================
    # HEATMAP SYNTHETIC DATA GENERATION
    # =========================================================================

    def generate_heatmap_data(self, user_role: str = "manager") -> dict:
        """
        Generates full heatmap and areas payloads matching location_server.py.
        Coordinates centered on iconic landmark / venue (e.g. 18.5204, 73.8567).
        """
        t = self._get_time_phase()
        osc = math.sin(t * 0.4)
        osc_fast = math.sin(t * 1.1)

        # Camera-derived spatial grid hotspots
        cells_meta = [
            {"cell_id": "18.5200_73.8570", "lat": 18.5204, "lon": 73.8567, "x": 0.50, "y": 0.50, "name": "Hotspot A (X: 0.50, Y: 0.50)"},
            {"cell_id": "18.5210_73.8570", "lat": 18.5214, "lon": 73.8567, "x": 0.50, "y": 0.20, "name": "Hotspot B (X: 0.50, Y: 0.20)"},
            {"cell_id": "18.5190_73.8570", "lat": 18.5194, "lon": 73.8567, "x": 0.50, "y": 0.80, "name": "Hotspot C (X: 0.50, Y: 0.80)"},
            {"cell_id": "18.5200_73.8580", "lat": 18.5204, "lon": 73.8577, "x": 0.80, "y": 0.50, "name": "Hotspot D (X: 0.80, Y: 0.50)"},
            {"cell_id": "18.5200_73.8560", "lat": 18.5204, "lon": 73.8557, "x": 0.20, "y": 0.50, "name": "Hotspot E (X: 0.20, Y: 0.50)"},
            {"cell_id": "18.5210_73.8580", "lat": 18.5214, "lon": 73.8577, "x": 0.80, "y": 0.20, "name": "Hotspot F (X: 0.80, Y: 0.20)"},
        ]

        if self.scenario == "normal":
            densities = [24, 18, 20, 15, 12, 8]
            trends = ["STABLE", "STABLE", "STABLE", "STABLE", "STABLE", "STABLE"]
            risk_levels = ["LOW", "LOW", "LOW", "LOW", "LOW", "LOW"]
            risk_scores = [18.0, 14.0, 16.0, 12.0, 10.0, 6.0]

        elif self.scenario == "buildup":
            densities = [
                int(68 + 8 * osc + 3 * osc_fast),
                int(42 + 5 * osc),
                int(54 + 6 * osc),
                int(32 + 4 * osc),
                int(26 + 3 * osc),
                int(14 + 2 * osc),
            ]
            trends = ["RISING", "RISING", "RISING", "STABLE", "STABLE", "STABLE"]
            risk_levels = ["HIGH", "MEDIUM", "HIGH", "LOW", "LOW", "LOW"]
            risk_scores = [74.0 + 4.0 * osc, 48.0 + 3.0 * osc, 66.0 + 5.0 * osc, 28.0, 22.0, 12.0]

        elif self.scenario == "critical":
            densities = [
                int(112 + 10 * osc + 5 * osc_fast),
                int(78 + 7 * osc),
                int(88 + 8 * osc),
                int(55 + 5 * osc),
                int(44 + 4 * osc),
                int(22 + 3 * osc),
            ]
            trends = ["RISING", "RISING", "RISING", "RISING", "STABLE", "STABLE"]
            risk_levels = ["CRITICAL", "HIGH", "CRITICAL", "MEDIUM", "MEDIUM", "LOW"]
            risk_scores = [94.0 + 3.0 * osc, 78.0 + 4.0 * osc, 88.0 + 3.0 * osc, 52.0, 46.0, 18.0]

        else:  # dispersal
            densities = [
                max(12, int(35 - 3 * osc)),
                max(8, int(22 - 2 * osc)),
                max(10, int(25 - 2 * osc)),
                max(14, int(38 + 4 * osc)),
                max(10, int(20 - 2 * osc)),
                max(16, int(32 + 3 * osc)),
            ]
            trends = ["FALLING", "FALLING", "FALLING", "STABLE", "FALLING", "RISING"]
            risk_levels = ["MEDIUM", "LOW", "LOW", "LOW", "LOW", "LOW"]
            risk_scores = [38.0, 20.0, 22.0, 24.0, 18.0, 22.0]

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

        cells = []
        areas = []

        for idx, m in enumerate(cells_meta):
            density = max(1, densities[idx])
            r_lvl = risk_levels[idx]
            r_score = round(max(5.0, min(float(risk_scores[idx]), 100.0)), 1)
            conf = round(min(density / 20.0, 1.0), 2)
            trend = trends[idx]

            # Public vs Manager recommendation
            if r_lvl == "CRITICAL":
                crowd_status = "Crowded"
                mgr_action = f"IMMEDIATE ACCESS CONTROL: Restrict inflow to {m['name']} | Direct crowd toward clear ground plane"
                user_action = f"High density in {m['name']}. Recommended alternate: open pathways."
                nav_guidance = "Area is currently busy. Follow wayfinding signs toward clear grounds."
            elif r_lvl == "HIGH":
                crowd_status = "Moderate"
                mgr_action = f"CROWD REDIRECTION: Deploy marshals at {m['name']} | Encourage movement toward open area"
                user_action = f"Moderate movement at {m['name']}. Clearer route available nearby."
                nav_guidance = "Smooth flow observed toward perimeter paths."
            elif r_lvl == "MEDIUM":
                crowd_status = "Moderate"
                mgr_action = f"MONITORING: Monitor {m['name']} ingress rates | Standby redirection"
                user_action = f"Moderate movement at {m['name']}."
                nav_guidance = "Open paths available."
            else:
                crowd_status = "Low"
                mgr_action = f"Normal operations at {m['name']}."
                user_action = f"Clear and smooth passage at {m['name']}."
                nav_guidance = "Clear walking path."

            if user_role == "manager":
                cell_dict = {
                    "cell_id": m["cell_id"],
                    "name": m["name"],
                    "latitude": m["lat"],
                    "longitude": m["lon"],
                    "lat": m["lat"],
                    "lon": m["lon"],
                    "density": density,
                    "active_sessions": density,
                    "confidence": conf,
                    "trend": trend,
                    "risk_score": r_score,
                    "risk_level": r_lvl,
                    "last_updated": now_iso,
                    "action": mgr_action,
                    "safe_alternative": "18.5210_73.8580" if r_lvl in ("HIGH", "CRITICAL") else None,
                }
            else:
                # Strictly sanitized Public User map cell - NO risk_score, NO risk_level (HIGH/CRITICAL), NO confidence, NO raw session counts
                cell_dict = {
                    "cell_id": m["cell_id"],
                    "name": m["name"],
                    "latitude": m["lat"],
                    "longitude": m["lon"],
                    "lat": m["lat"],
                    "lon": m["lon"],
                    "crowd_status": crowd_status,
                    "safe_guidance": user_action,
                    "wayfinding": nav_guidance,
                    "safer_area": "Northeast Overflow Grounds" if crowd_status == "Crowded" else None,
                    "last_updated": now_iso,
                }

            cells.append(cell_dict)

            # Area alert / nearby safer areas
            if user_role == "manager":
                if r_lvl in ("MEDIUM", "HIGH", "CRITICAL"):
                    areas.append({
                        "source": "location",
                        "area": m["name"],
                        "cell_id": m["cell_id"],
                        "name": m["name"],
                        "latitude": m["lat"],
                        "longitude": m["lon"],
                        "lat": m["lat"],
                        "lon": m["lon"],
                        "density": density,
                        "risk_level": r_lvl,
                        "risk_score": r_score,
                        "trend": trend,
                        "risk_cause": "High GPS signal concentration + upward surge",
                        "possible_origin": "Central Plaza & Main Gate" if m["cell_id"] != "18.5200_73.8570" else "East Transit Hub",
                        "safe_alternative": "Northeast Overflow Grounds",
                        "recommended_action": mgr_action,
                    })
            else:
                # Public user nearby safer areas suggestions (non-alarming notification format)
                if crowd_status in ("Moderate", "Crowded"):
                    areas.append({
                        "source": "location",
                        "area": m["name"],
                        "cell_id": m["cell_id"],
                        "area_name": m["name"],
                        "name": m["name"],
                        "latitude": m["lat"],
                        "longitude": m["lon"],
                        "lat": m["lat"],
                        "lon": m["lon"],
                        "crowd_status": crowd_status,
                        "safe_alternative": "Northeast Overflow Grounds",
                        "suggested_safer_area": "Northeast Overflow Grounds",
                        "navigation_hint": f"Follow directional signs away from {m['name']} to reach clear grounds.",
                        "recommended_action": user_action,
                    })

        if user_role == "manager":
            cells.sort(key=lambda c: c["density"], reverse=True)
            areas.sort(key=lambda a: a["risk_score"], reverse=True)

        return {
            "heatmap": {
                "timestamp": now_iso,
                "role": user_role,
                "demo_mode": True,
                "demo_scenario": self.scenario,
                "cell_count": len(cells),
                "cells": cells,
            },
            "areas": {
                "timestamp": now_iso,
                "role": user_role,
                "demo_mode": True,
                "demo_scenario": self.scenario,
                "area_count": len(areas),
                "areas": areas,
            },
            "status": {
                "status": "active",
                "role": user_role,
                "demo_mode": True,
                "demo_scenario": self.scenario,
                "total_cells": len(cells),
                "visible_cells": len(cells),
                "active_sessions": sum(c.get("density", 0) for c in cells) if user_role == "manager" else None,
                "timestamp": now_iso,
            },
        }


# Global singleton demo generator instance
demo_generator = DemoDataGenerator()
