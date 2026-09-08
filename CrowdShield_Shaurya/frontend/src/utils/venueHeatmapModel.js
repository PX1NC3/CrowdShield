/**
 * venueHeatmapModel.js
 * 
 * Shared Unified Data Model for CrowdShield Venue Heatmap (2D & 3D).
 * Transforms raw backend/demo cell data into a normalized rectangular venue coordinate space [0, 1] x [0, 1].
 * Provides continuous field interpolation for both 2D canvas and 3D Three.js terrain.
 */

// Camera-derived visible venue model info
export const CAMERA_VENUE_INFO = {
  name: 'Camera-Derived Visible Ground Model',
  code: 'CAMERA-DERIVED SPATIAL MODEL',
  subtitle: 'Spatial Data: Real Detections',
  coordinateSystem: 'Normalized Visible Ground Plane [0, 1] × [0, 1]',
  opticalAxes: 'X: 0.00 (West/Left) → 1.00 (East/Right), Y: 0.00 (North/Top) → 1.00 (South/Bottom)',
};
export const VENUE_INFO = CAMERA_VENUE_INFO;

// Risk color palette (CrowdShield standard)
export const RISK_PALETTE = {
  LOW: {
    label: 'LOW',
    hex: '#22c55e',
    rgb: [34, 197, 94],
    threeColor: 0x22c55e,
    desc: 'Normal density, smooth flow',
  },
  MEDIUM: {
    label: 'MODERATE',
    hex: '#eab308',
    rgb: [234, 179, 8],
    threeColor: 0xeab308,
    desc: 'Moderate traffic, rising pace',
  },
  HIGH: {
    label: 'HIGH',
    hex: '#f97316',
    rgb: [249, 115, 22],
    threeColor: 0xf97316,
    desc: 'High density, bottleneck alert',
  },
  CRITICAL: {
    label: 'CRITICAL',
    hex: '#ef4444',
    rgb: [239, 68, 68],
    threeColor: 0xef4444,
    desc: 'Severe crush risk, diversion active',
  },
};

/**
 * Maps a numeric risk score (0-100) or risk level to a normalized [0, 1] value.
 */
export function normalizeRiskScore(cell) {
  if (typeof cell.risk_score === 'number' && !isNaN(cell.risk_score)) {
    return Math.max(0, Math.min(100, cell.risk_score));
  }
  const lvl = (cell.risk_level || '').toUpperCase();
  if (lvl === 'CRITICAL') return 90;
  if (lvl === 'HIGH') return 70;
  if (lvl === 'MEDIUM' || lvl === 'MODERATE') return 45;
  if (cell.crowd_status === 'Crowded') return 80;
  if (cell.crowd_status === 'Moderate') return 45;
  return 15;
}

/**
 * Determines the risk level from a numeric score or property.
 */
export function getRiskLevelFromScore(score) {
  if (score >= 75) return 'CRITICAL';
  if (score >= 55) return 'HIGH';
  if (score >= 35) return 'MEDIUM';
  return 'LOW';
}

/**
 * Maps risk level to color string or object.
 */
export function getRiskColor(level) {
  const key = (level || 'LOW').toUpperCase();
  return RISK_PALETTE[key] || (key === 'MODERATE' ? RISK_PALETTE.MEDIUM : RISK_PALETTE.LOW);
}

/**
 * Interpolates risk score (0-100) into a continuous RGB color.
 */
export function interpolateRiskRgb(score) {
  const s = Math.max(0, Math.min(100, score));
  if (s <= 25) {
    // 0..25: Green
    return [34, 197, 94];
  } else if (s <= 55) {
    // 25..55: Green -> Yellow
    const t = (s - 25) / 30;
    return [
      Math.round(34 + t * (234 - 34)),
      Math.round(197 + t * (179 - 197)),
      Math.round(94 + t * (8 - 94)),
    ];
  } else if (s <= 75) {
    // 55..75: Yellow -> Orange
    const t = (s - 55) / 20;
    return [
      Math.round(234 + t * (249 - 234)),
      Math.round(179 + t * (115 - 179)),
      Math.round(8 + t * (22 - 8)),
    ];
  } else {
    // 75..100: Orange -> Red
    const t = Math.min(1, (s - 75) / 25);
    return [
      Math.round(249 + t * (239 - 249)),
      Math.round(115 + t * (68 - 115)),
      Math.round(22 + t * (68 - 22)),
    ];
  }
}

/**
 * Normalizes raw cell collection into the canonical venue coordinate space [0, 1] x [0, 1].
 * Both 2D and 3D visualizers consume this exact unified representation.
 */
export function normalizeHeatmapData(cells = [], role = 'manager') {
  if (!Array.isArray(cells) || cells.length === 0) return [];

  // Filter valid cells
  const validCells = cells.filter(c => Boolean(c));
  if (validCells.length === 0) return [];

  // Check if any cells need dynamic lat/lon projection
  let minLat = Infinity, maxLat = -Infinity, minLon = Infinity, maxLon = -Infinity;
  validCells.forEach(c => {
    const lat = Number(c.lat ?? c.latitude);
    const lon = Number(c.lon ?? c.longitude);
    if (!isNaN(lat) && !isNaN(lon)) {
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
      if (lon < minLon) minLon = lon;
      if (lon > maxLon) maxLon = lon;
    }
  });

  const latSpan = maxLat - minLat;
  const lonSpan = maxLon - minLon;

  return validCells.map((cell, idx) => {
    const cellId = String(cell.cell_id || `cell-${idx}`);
    const name = cell.name || cell.zone || cellId;

    // 1. Resolve normalized camera ground-plane coordinates [0, 1] x [0, 1]
    let normX = 0.5;
    let normY = 0.5;

    if (typeof cell.x === 'number' && typeof cell.y === 'number' && !isNaN(cell.x) && !isNaN(cell.y)) {
      // Direct camera-derived ground coordinate
      normX = Math.max(0.04, Math.min(0.96, cell.x));
      normY = Math.max(0.04, Math.min(0.96, cell.y));
    } else {
      // Dynamic projection from lat/lon if provided
      const lat = Number(cell.lat ?? cell.latitude);
      const lon = Number(cell.lon ?? cell.longitude);
      if (!isNaN(lat) && !isNaN(lon) && latSpan > 0.00001 && lonSpan > 0.00001) {
        normX = 0.15 + 0.70 * ((lon - minLon) / lonSpan);
        normY = 0.15 + 0.70 * (1.0 - (lat - minLat) / latSpan);
      } else {
        const angle = (idx / Math.max(1, validCells.length)) * Math.PI * 2;
        normX = 0.50 + 0.30 * Math.cos(angle);
        normY = 0.50 + 0.30 * Math.sin(angle);
      }
    }

    const spatialCoord = cell.spatial_coord || `X ${normX.toFixed(2)} / Y ${normY.toFixed(2)}`;
    const sectorName = `Ground Region (${spatialCoord})`;

    // 2. Resolve density count
    const density = Number(cell.density ?? cell.active_sessions ?? (cell.crowd_status === 'Crowded' ? 85 : (cell.crowd_status === 'Moderate' ? 45 : 15))) || 0;

    // 3. Resolve risk score and level
    const riskScore = normalizeRiskScore(cell);
    const rawLevel = (cell.risk_level || '').toUpperCase();
    const riskLevel = rawLevel === 'CRITICAL' || rawLevel === 'HIGH' || rawLevel === 'MEDIUM' || rawLevel === 'LOW'
      ? rawLevel
      : getRiskLevelFromScore(riskScore);

    const crowdStatus = cell.crowd_status || (riskLevel === 'CRITICAL' ? 'Crowded' : (riskLevel === 'HIGH' || riskLevel === 'MEDIUM' ? 'Moderate' : 'Low'));

    // Safe alternative target
    const safeAltId = cell.safe_alternative || cell.safer_area || null;

    return {
      id: cellId,
      name,
      sector: sectorName,
      x: normX,
      y: normY,
      density,
      riskScore,
      riskLevel,
      crowdStatus,
      spatialCoord,
      spatialRegion: `Ground Region (${spatialCoord})`,
      trend: cell.trend || 'STABLE',
      trendDelta: cell.trend_delta || 0,
      confidence: cell.confidence ?? 0.9,
      riskCause: cell.risk_cause || (riskLevel === 'CRITICAL' ? 'High density concentration in camera view' : 'Normal flow'),
      action: cell.action || cell.safe_guidance || (riskLevel === 'CRITICAL' ? 'High density alert — direct flow toward open ground' : 'Proceed along clear ground lanes'),
      safeAlternative: safeAltId,
      raw: cell,
    };
  });
}

/**
 * Continuous spatial field evaluator for both 2D and 3D rendering.
 * Evaluates the continuous crowd density and risk score at any normalized coordinate (x, y) in [0, 1].
 * Uses Gaussian Radial Basis Function (RBF) decay.
 */
export function evaluateFieldAt(x, y, points, sigma = 0.13) {
  if (!points || points.length === 0) {
    return { density: 0, riskScore: 0, highestRiskLevel: 'LOW' };
  }

  let totalDensity = 0;
  let weightedRisk = 0;
  let totalWeight = 0;
  const twoSigmaSq = 2 * sigma * sigma;

  for (let i = 0; i < points.length; i++) {
    const pt = points[i];
    const dx = x - pt.x;
    const dy = y - pt.y;
    const distSq = dx * dx + dy * dy;
    const weight = Math.exp(-distSq / twoSigmaSq);

    totalDensity += pt.density * weight;
    weightedRisk += pt.riskScore * weight;
    totalWeight += weight;
  }

  const avgRisk = totalWeight > 0.001 ? (weightedRisk / totalWeight) : 0;
  return {
    density: totalDensity,
    riskScore: avgRisk,
    highestRiskLevel: getRiskLevelFromScore(avgRisk),
  };
}

export const BASE_GROUND_RGB = [18, 28, 48]; // Deep tactical slate

/**
 * Maps crowd density to 3D terrain visual height.
 * Uses nonlinear amplification:
 *   normalizedDensity = density / maxDensity
 *   heightFactor = Math.pow(normalizedDensity, 0.65)
 *   height = MIN_HEIGHT + heightFactor * (MAX_HEIGHT - MIN_HEIGHT)
 *
 * Low density -> nearly flat baseline (0.08 - 0.4)
 * Moderate density -> clearly raised (1.8 - 3.2)
 * High density -> prominent hill (3.5 - 4.8)
 * Critical density -> obvious peak (5.0 - 6.5)
 */
export function densityToHeight(density, maxDensity = 10, maxHeight = 5.2, minHeight = 0.08) {
  if (!density || density <= 0.005) return minHeight;
  const effectiveMax = Math.max(2.5, maxDensity);
  const normalized = Math.min(1.0, Math.max(0, density / effectiveMax));
  const heightFactor = Math.pow(normalized, 0.65);
  return minHeight + heightFactor * (maxHeight - minHeight);
}

/**
 * Computes 3D vertex color by blending dark base ground with risk color
 * according to local crowd density / height relief.
 * Where density is near zero, terrain is sleek dark tactical ground.
 * Where crowd forms, it rises into emerald -> yellow -> orange -> red.
 */
export function getTerrainVertexRgb(riskScore, densityNorm = 0) {
  const [riskR, riskG, riskB] = interpolateRiskRgb(riskScore);
  if (densityNorm <= 0.005) {
    return [BASE_GROUND_RGB[0] / 255, BASE_GROUND_RGB[1] / 255, BASE_GROUND_RGB[2] / 255];
  }
  const t = Math.min(1.0, Math.max(0, Math.pow(densityNorm, 0.7) * 1.3));
  const r = (BASE_GROUND_RGB[0] + t * (riskR - BASE_GROUND_RGB[0])) / 255;
  const g = (BASE_GROUND_RGB[1] + t * (riskG - BASE_GROUND_RGB[1])) / 255;
  const b = (BASE_GROUND_RGB[2] + t * (riskB - BASE_GROUND_RGB[2])) / 255;
  return [r, g, b];
}

