"""
CrowdShield — Shared Risk & Prevention Engine
=============================================
Pure-Python functions extracted from detect.py so that both the camera
detection pipeline and the location aggregation server can use the same
risk/prevention logic without duplication.

All functions here are stateless with respect to the calling module.
State (baselines, samples) lives in AdaptiveBaseline instances.
"""

# =====================================================
# ADAPTIVE BASELINE ENGINE
# =====================================================

class AdaptiveBaseline:
    """Per-zone (or per-cell) online mean/std estimator.

    Keeps a rolling window of `window_size` recent density samples
    and maintains an exponentially-smoothed mean and std.
    """

    def __init__(
        self,
        min_samples: int = 30,
        window_size: int = 120,
        alpha: float = 0.05,
    ):
        self.min_samples = min_samples
        self.window_size = window_size
        self.alpha = alpha

        self.mean = None
        self.std = None
        self._samples: list[float] = []

    def update(self, value: float) -> None:
        self._samples.append(float(value))
        if len(self._samples) > self.window_size:
            self._samples.pop(0)

        if len(self._samples) >= self.min_samples:
            mean = sum(self._samples) / len(self._samples)
            variance = (
                sum((x - mean) ** 2 for x in self._samples)
                / len(self._samples)
            )
            std = max(variance ** 0.5, 1.0)

            if self.mean is None:
                self.mean = mean
                self.std = std
            else:
                self.mean = (1 - self.alpha) * self.mean + self.alpha * mean
                self.std = (1 - self.alpha) * self.std + self.alpha * std

    def deviation(self, value: float) -> float:
        """Return how many std-deviations `value` is above the learned mean."""
        if self.mean is None or self.std is None:
            return 0.0
        return (float(value) - self.mean) / max(self.std, 1.0)

    def as_dict(self) -> dict:
        return {
            "mean": round(self.mean, 3) if self.mean is not None else None,
            "std": round(self.std, 3) if self.std is not None else None,
            "samples": len(self._samples),
        }


# =====================================================
# ADAPTIVE RISK ENGINE
# =====================================================

def calculate_adaptive_risk(
    density: float,
    density_change: float,
    incoming: float,
    outgoing: float,
    density_deviation: float,
    incoming_deviation: float,
    outgoing_deviation: float,
    density_std: float,
) -> tuple[float, str]:
    """Return (risk_score 0–100, risk_level string).

    Risk is measured against learned normal behaviour.
    No fixed population threshold is used.
    """
    density_anomaly = max(density_deviation, 0.0)
    incoming_anomaly = max(incoming_deviation, 0.0)
    outgoing_anomaly = max(outgoing_deviation, 0.0)
    growth_anomaly = max(density_change, 0.0) / max(density_std, 1.0)

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

    strongest_anomaly = max(density_anomaly, growth_anomaly, incoming_anomaly)

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
# RISK CAUSE ANALYSIS
# =====================================================

def identify_risk_cause(
    density: float,
    density_change: float,
    incoming: float,
    outgoing: float,
    density_deviation: float,
    incoming_deviation: float,
) -> str:
    """Return a human-readable description of what is driving risk."""
    causes = []

    if density_change > 0:
        causes.append("Density increasing")

    if density_change >= 0.8:
        causes.append("Rapid density increase")

    if incoming_deviation >= 1.0 and incoming > outgoing:
        causes.append("High incoming crowd flow")

    if density_change > 0 and incoming > outgoing:
        causes.append("Sustained crowd build-up")

    if density_deviation >= 1.0:
        causes.append("Density above learned baseline")

    if not causes:
        if density_deviation > 0 or incoming_deviation > 0:
            return "Mild abnormal crowd behaviour"
        return "Normal crowd conditions"

    return " + ".join(causes)


# =====================================================
# SAFE ALTERNATIVE ZONE / AREA SELECTION
# =====================================================

def select_safe_alternative_zone(
    target_idx: int,
    origin_idx: int | None,
    risk_scores: list[float],
    zone_counts: list[float],
    n_zones: int = 9,
) -> str | None:
    """Return the label of the safest currently available zone.

    `target_idx` and `origin_idx` are zero-based indexes (0..n_zones-1).
    Returns None if no safe alternative can be found.
    """
    if not (0 <= int(target_idx) < n_zones):
        return None

    if origin_idx is not None and not (0 <= int(origin_idx) < n_zones):
        return None

    if len(risk_scores) != n_zones or len(zone_counts) != n_zones:
        return None

    candidates = []

    for i in range(n_zones):
        if i == int(target_idx) or (
            origin_idx is not None and i == int(origin_idx)
        ):
            continue

        risk = float(risk_scores[i])
        density = float(zone_counts[i])

        if risk >= 50.0:
            continue

        safety_score = (100.0 - risk) + (100.0 - min(density, 100.0))
        candidates.append((safety_score, i, risk, density))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    best_idx = candidates[0][1]
    return f"Z{best_idx + 1}"


def select_safe_alternative_area(
    target_id: str,
    origin_id: str | None,
    candidate_areas: list[dict],
) -> str | None:
    """Dynamically select the safest nearby alternative area/cell.

    Each candidate dict should have:
    - area_id: str
    - risk_score: float (0-100)
    - density: float/int
    - trend: str (optional, RISING/FALLING/STABLE)

    Returns the area_id of the safest candidate, or None.
    """
    valid_candidates = []
    for cand in candidate_areas:
        c_id = cand.get("area_id") or cand.get("cell_id") or cand.get("name")
        if not c_id:
            continue
        if c_id == target_id or (origin_id is not None and c_id == origin_id):
            continue

        risk = float(cand.get("risk_score", 0.0))
        if risk >= 50.0:
            continue
        density = float(cand.get("density", 0.0))
        trend = cand.get("trend", "STABLE")

        # Trend penalty/bonus
        trend_penalty = 10.0 if trend == "RISING" else (-5.0 if trend == "FALLING" else 0.0)

        # Higher safety score is better
        safety_score = (100.0 - risk) + (100.0 - min(density, 100.0)) - trend_penalty
        valid_candidates.append((safety_score, c_id, risk, density))

    if not valid_candidates:
        return None

    valid_candidates.sort(reverse=True)
    return valid_candidates[0][1]


# =====================================================
# PREVENTION ACTION STRING
# =====================================================

def generate_action_string(
    risk_level: str,
    zone_label: str,
    safe_alternative: str | None,
) -> str:
    """Generate a human-readable prevention action string."""
    alt = safe_alternative or "an alternative area"

    if risk_level == "CRITICAL":
        return (
            f"IMMEDIATE DIVERSION | Restrict entry to {zone_label} | "
            f"Alert operator | Redirect to {alt}"
        )
    elif risk_level == "HIGH":
        return (
            f"REDIRECT CROWD | Restrict inflow to {zone_label} | "
            f"Move toward {alt}"
        )
    elif risk_level == "MEDIUM":
        return (
            f"PREPARE REDIRECTION | Monitor {zone_label} | "
            f"Prefer {alt} if density rises"
        )
    else:
        return "No action required. Continue monitoring."


# =====================================================
# Z-SCORE HELPER
# =====================================================

def z_score(value: float, mean: float | None, std: float | None) -> float:
    if mean is None or std is None:
        return 0.0
    return (float(value) - mean) / max(std, 1.0)


# =====================================================
# DENSITY TREND HELPER
# =====================================================

TREND_THRESHOLD = 0.5


def compute_trend(history: list[float]) -> tuple[str, float]:
    """Return (trend_label, delta) from a list of recent density values."""
    if len(history) < 6:
        return "STABLE", 0.0

    midpoint = len(history) // 2
    first_avg = sum(history[:midpoint]) / midpoint
    second_half = history[midpoint:]
    second_avg = sum(second_half) / len(second_half)
    delta = second_avg - first_avg

    if delta > TREND_THRESHOLD:
        return "RISING", delta
    elif delta < -TREND_THRESHOLD:
        return "FALLING", delta
    else:
        return "STABLE", delta
