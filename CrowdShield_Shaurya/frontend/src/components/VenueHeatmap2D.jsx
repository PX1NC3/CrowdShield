/**
 * VenueHeatmap2D.jsx
 * 
 * High-performance 2D Camera-Derived Venue Crowd Intelligence Heatmap.
 * Renders the visible ground plane derived from real camera footage and YOLOv8 detections.
 * 
 * Pipeline:
 * Real Video -> YOLOv8n + ByteTrack -> Real Person Centroids -> Visible Ground Plane [0, 1] x [0, 1]
 * -> Continuous Gaussian Heat Surface -> Tactical 2D Heatmap
 */

import { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import { interpolateRiskRgb, RISK_PALETTE, CAMERA_VENUE_INFO } from '../utils/venueHeatmapModel';
import './VenueHeatmap2D.css';

export default function VenueHeatmap2D({
  points = [],
  detections = [],
  cameraInfo = null,
  selectedPoint = null,
  onSelectPoint = null,
  isManager = true,
  filter = 'ALL',
}) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const animFrameRef = useRef(null);
  const pulsePhaseRef = useRef(0);

  const [hoveredPoint, setHoveredPoint] = useState(null);
  const [tooltipPos, setTooltipPos] = useState(null);
  const [mouseNorm, setMouseNorm] = useState(null);

  // Filter points based on active filter
  const filteredPoints = useMemo(() => {
    return points.filter(pt => {
      if (filter === 'HIGH') return pt.riskLevel === 'HIGH' || pt.riskLevel === 'CRITICAL';
      if (filter === 'CRITICAL') return pt.riskLevel === 'CRITICAL';
      if (filter === 'MODERATE') return pt.riskLevel === 'MEDIUM' || pt.crowdStatus === 'Moderate' || pt.crowdStatus === 'Crowded';
      if (filter === 'CROWDED') return pt.crowdStatus === 'Crowded' || pt.riskLevel === 'CRITICAL';
      return true;
    });
  }, [points, filter]);

  // Main Canvas Rendering Loop
  const renderCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = container.clientWidth;
    const height = container.clientHeight;
    const dpr = window.devicePixelRatio || 1;

    // Handle high-DPI scaling
    if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
      canvas.width = width * dpr;
      canvas.height = height * dpr;
    }

    ctx.save();
    ctx.scale(dpr, dpr);

    // Operational boundary margins
    const padX = Math.max(42, width * 0.07);
    const padY = Math.max(46, height * 0.09);
    const venueW = width - padX * 2;
    const venueH = height - padY * 2;

    const toScreenX = (nx) => padX + nx * venueW;
    const toScreenY = (ny) => padY + ny * venueH;

    // ── 1. Clear & Deep Tactical Background ────────────────────
    ctx.fillStyle = '#090d16';
    ctx.fillRect(0, 0, width, height);

    // Subtle background grid lines
    ctx.strokeStyle = 'rgba(30, 41, 59, 0.4)';
    ctx.lineWidth = 1;
    const gridSpacing = 32;
    for (let x = 0; x < width; x += gridSpacing) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = 0; y < height; y += gridSpacing) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    // ── 2. Visible Camera Ground-Plane Frame ────────────────────
    // Ground plane fill
    ctx.fillStyle = 'rgba(15, 23, 42, 0.55)';
    ctx.fillRect(padX, padY, venueW, venueH);

    // Subtle optical perspective / normalized coordinate grid [0, 1]
    const divisions = 4;
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.12)';
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);

    for (let i = 1; i < divisions; i++) {
      const gx = padX + (i / divisions) * venueW;
      const gy = padY + (i / divisions) * venueH;

      // Vertical line
      ctx.beginPath();
      ctx.moveTo(gx, padY);
      ctx.lineTo(gx, padY + venueH);
      ctx.stroke();

      // Horizontal line
      ctx.beginPath();
      ctx.moveTo(padX, gy);
      ctx.lineTo(padX + venueW, gy);
      ctx.stroke();
    }
    ctx.setLineDash([]);

    // Axis tick labels along the ground-plane frame
    ctx.fillStyle = 'rgba(148, 163, 184, 0.5)';
    ctx.font = '600 8px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';
    for (let i = 0; i <= divisions; i++) {
      const frac = (i / divisions).toFixed(2);
      const gx = padX + (i / divisions) * venueW;
      ctx.fillText(`X:${frac}`, gx, padY + venueH + 12);
    }
    ctx.textAlign = 'right';
    for (let i = 0; i <= divisions; i++) {
      const frac = (i / divisions).toFixed(2);
      const gy = padY + (i / divisions) * venueH;
      ctx.fillText(`Y:${frac}`, padX - 6, gy + 3);
    }

    // Outer Ground-Plane Boundary Frame
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
    ctx.lineWidth = 1;
    ctx.strokeRect(padX, padY, venueW, venueH);

    // Subtle corner framing accents
    const bracketLen = 12;
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.25)';
    ctx.lineWidth = 1.5;
    // Top-Left
    ctx.beginPath();
    ctx.moveTo(padX - 2, padY + bracketLen);
    ctx.lineTo(padX - 2, padY - 2);
    ctx.lineTo(padX + bracketLen, padY - 2);
    ctx.stroke();
    // Top-Right
    ctx.beginPath();
    ctx.moveTo(padX + venueW + 2, padY + bracketLen);
    ctx.lineTo(padX + venueW + 2, padY - 2);
    ctx.lineTo(padX + venueW - bracketLen, padY - 2);
    ctx.stroke();
    // Bottom-Left
    ctx.beginPath();
    ctx.moveTo(padX - 2, padY + venueH - bracketLen);
    ctx.lineTo(padX - 2, padY + venueH + 2);
    ctx.lineTo(padX + bracketLen, padY + venueH + 2);
    ctx.stroke();
    // Bottom-Right
    ctx.beginPath();
    ctx.moveTo(padX + venueW + 2, padY + venueH - bracketLen);
    ctx.lineTo(padX + venueW + 2, padY + venueH + 2);
    ctx.lineTo(padX + venueW - bracketLen, padY + venueH + 2);
    ctx.stroke();

    // ── 3. CONTINUOUS HEAT SURFACE RENDERING ──────────────────
    // Continuous crowd field evaluated from real person positions / clustered hotspots
    if (filteredPoints.length > 0) {
      ctx.save();
      // 'screen' blend mode composites overlapping Gaussian auras smoothly
      ctx.globalCompositeOperation = 'screen';

      filteredPoints.forEach((pt) => {
        const px = toScreenX(pt.x);
        const py = toScreenY(pt.y);

        // Radius scaled by density and dimensions
        const baseRadius = Math.min(venueW, venueH) * 0.32;
        const densityFactor = Math.min(1.4, Math.max(0.65, Math.sqrt(pt.density / 25)));
        const radius = baseRadius * densityFactor;

        // Color interpolation based on risk score
        const [r, g, b] = interpolateRiskRgb(pt.riskScore);
        const pulse = 1.0 + 0.04 * Math.sin(pulsePhaseRef.current + pt.x * 5);

        // Core continuous radial gradient
        const grad = ctx.createRadialGradient(px, py, 0, px, py, radius * pulse);
        const peakAlpha = Math.min(0.85, 0.35 + (pt.density / 80) * 0.45);
        grad.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${peakAlpha})`);
        grad.addColorStop(0.25, `rgba(${r}, ${g}, ${b}, ${peakAlpha * 0.7})`);
        grad.addColorStop(0.55, `rgba(${r}, ${g}, ${b}, ${peakAlpha * 0.35})`);
        grad.addColorStop(0.85, `rgba(${r}, ${g}, ${b}, ${peakAlpha * 0.1})`);
        grad.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);

        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(px, py, radius * pulse, 0, Math.PI * 2);
        ctx.fill();
      });

      ctx.restore();

      // Topographic contour rings around intense hotspots
      ctx.save();
      filteredPoints.forEach((pt) => {
        if (pt.riskScore >= 40 || pt.density >= 5) {
          const px = toScreenX(pt.x);
          const py = toScreenY(pt.y);
          const [r, g, b] = interpolateRiskRgb(pt.riskScore);
          const baseRadius = Math.min(venueW, venueH) * 0.22;
          const pulse = 1.0 + 0.03 * Math.sin(pulsePhaseRef.current * 1.5 + pt.y * 4);

          // Inner contour
          ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, 0.28)`;
          ctx.lineWidth = 1;
          ctx.setLineDash([4, 4]);
          ctx.beginPath();
          ctx.arc(px, py, baseRadius * 0.5 * pulse, 0, Math.PI * 2);
          ctx.stroke();

          // Outer contour
          ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, 0.16)`;
          ctx.beginPath();
          ctx.arc(px, py, baseRadius * 0.85 * pulse, 0, Math.PI * 2);
          ctx.stroke();
          ctx.setLineDash([]);
        }
      });
      ctx.restore();
    }

    // ── 4. REAL PERSON CENTROID DETECTIONS ─────────────────────
    // Render individual detected people as discrete glowing centroids
    if (Array.isArray(detections) && detections.length > 0) {
      ctx.save();
      detections.forEach((det) => {
        const dx = toScreenX(det.x);
        const dy = toScreenY(det.y);

        // Person centroid indicator
        ctx.fillStyle = 'rgba(255, 255, 255, 0.18)';
        ctx.beginPath();
        ctx.arc(dx, dy, 4.5, 0, Math.PI * 2);
        ctx.fill();

        // Core person dot
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(dx, dy, 2, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.restore();
    }

    // ── 5. Safe Guidance Vectors ───────────────────────────────
    filteredPoints.forEach((pt) => {
      const isUrgent = pt.riskLevel === 'HIGH' || pt.riskLevel === 'CRITICAL' || pt.crowdStatus === 'Crowded';
      const isSelected = selectedPoint?.id === pt.id;
      if (!isUrgent && !isSelected) return;

      const altTarget = pt.safeAlternative;
      if (!altTarget) return;

      const targetPt = points.find(p => p.id === altTarget || p.name === altTarget);
      if (!targetPt) return;

      const x1 = toScreenX(pt.x);
      const y1 = toScreenY(pt.y);
      const x2 = toScreenX(targetPt.x);
      const y2 = toScreenY(targetPt.y);

      ctx.save();
      ctx.strokeStyle = '#10b981';
      ctx.lineWidth = isSelected ? 2.5 : 1.5;
      ctx.setLineDash([6, 6]);
      ctx.lineDashOffset = -pulsePhaseRef.current * 8;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      const midX = (x1 + x2) / 2;
      const midY = (y1 + y2) / 2 - 15;
      ctx.quadraticCurveTo(midX, midY, x2, y2);
      ctx.stroke();

      const angle = Math.atan2(y2 - midY, x2 - midX);
      ctx.fillStyle = '#10b981';
      ctx.beginPath();
      ctx.moveTo(x2, y2);
      ctx.lineTo(x2 - 8 * Math.cos(angle - Math.PI / 6), y2 - 8 * Math.sin(angle - Math.PI / 6));
      ctx.lineTo(x2 - 8 * Math.cos(angle + Math.PI / 6), y2 - 8 * Math.sin(angle + Math.PI / 6));
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    });

    // ── 6. REAL HOTSPOT CLUSTER BEACONS & DATA BADGES ──────────
    filteredPoints.forEach((pt) => {
      const px = toScreenX(pt.x);
      const py = toScreenY(pt.y);
      const isSelected = selectedPoint?.id === pt.id;
      const isHovered = hoveredPoint?.id === pt.id;
      const [r, g, b] = interpolateRiskRgb(pt.riskScore);

      ctx.save();

      // Center glowing beacon dot
      ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
      ctx.shadowColor = `rgba(${r}, ${g}, ${b}, 0.8)`;
      ctx.shadowBlur = isSelected ? 16 : (isHovered ? 12 : 6);
      ctx.beginPath();
      ctx.arc(px, py, isSelected ? 7 : (isHovered ? 6 : 4.5), 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      // Selection pulse ring
      if (isSelected || isHovered) {
        ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, 0.85)`;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(px, py, (isSelected ? 16 : 12) + Math.sin(pulsePhaseRef.current * 3) * 2, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Compact Venue Hotspot Tag (No fictional names!)
      const tagText = pt.name;
      const metricText = isManager
        ? `DENSITY: ${pt.density} · ${pt.riskLevel}`
        : `STATUS: ${pt.crowdStatus}`;

      ctx.font = '700 10px "Inter", sans-serif';
      const textWidth = Math.max(ctx.measureText(tagText).width, ctx.measureText(metricText).width);
      const badgeW = textWidth + 18;
      const badgeH = 28;
      const badgeX = px - badgeW / 2;
      const badgeY = py - 38;

      // Badge background
      ctx.fillStyle = 'rgba(15, 23, 42, 0.92)';
      ctx.strokeStyle = isSelected ? `rgb(${r}, ${g}, ${b})` : 'rgba(255, 255, 255, 0.18)';
      ctx.lineWidth = isSelected ? 1.5 : 1;
      ctx.beginPath();
      ctx.roundRect(badgeX, badgeY, badgeW, badgeH, 4);
      ctx.fill();
      ctx.stroke();

      // Connecting pointer line
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.25)';
      ctx.beginPath();
      ctx.moveTo(px, badgeY + badgeH);
      ctx.lineTo(px, py - 6);
      ctx.stroke();

      // Badge Title
      ctx.fillStyle = '#ffffff';
      ctx.textAlign = 'center';
      ctx.font = '700 9px "Inter", sans-serif';
      ctx.fillText(tagText, px, badgeY + 11);

      // Badge Subtitle
      ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
      ctx.font = '700 9px "JetBrains Mono", monospace';
      ctx.fillText(metricText, px, badgeY + 23);

      ctx.restore();
    });

    // ── 7. Camera Tactical HUD Overlays ───────────────────────
    ctx.save();

    // Top-Left: Model & Source Badges
    ctx.fillStyle = 'rgba(255, 255, 255, 0.95)';
    ctx.font = '700 10px "JetBrains Mono", monospace';
    ctx.textAlign = 'left';
    ctx.fillText('CAMERA-DERIVED VENUE MODEL', padX + 6, padY - 24);

    ctx.fillStyle = 'rgba(148, 163, 184, 0.85)';
    ctx.font = '600 9px "JetBrains Mono", monospace';
    const totalDets = Array.isArray(detections) && detections.length > 0
      ? detections.length
      : points.reduce((acc, p) => acc + (p.density || 0), 0);
    const camLabel = cameraInfo?.name || 'ACTIVE CAMERA VIEW';
    ctx.fillText(`SPATIAL DATA: REAL DETECTIONS · ${camLabel.toUpperCase()} · ${totalDets} DETECTIONS`, padX + 6, padY - 10);

    // Top-Right: Camera Optical Field Reference
    const compassX = padX + venueW - 10;
    ctx.textAlign = 'right';
    ctx.fillStyle = 'rgba(255, 255, 255, 0.75)';
    ctx.font = 'bold 9px "JetBrains Mono", monospace';
    ctx.fillText('▲ FORWARD OPTICAL AXIS', compassX, padY - 14);

    ctx.fillStyle = 'rgba(148, 163, 184, 0.6)';
    ctx.font = '600 8px "JetBrains Mono", monospace';
    ctx.fillText('GROUND PLANE X: [0.00-1.00] · Y: [0.00-1.00]', compassX, padY - 4);

    ctx.restore();

    ctx.restore();
  }, [filteredPoints, detections, points, selectedPoint, hoveredPoint, cameraInfo, isManager]);

  // Animation frame for glowing pulses
  useEffect(() => {
    let active = true;
    const loop = () => {
      if (!active) return;
      pulsePhaseRef.current += 0.035;
      renderCanvas();
      animFrameRef.current = requestAnimationFrame(loop);
    };
    loop();
    return () => {
      active = false;
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [renderCanvas]);

  // Window Resize Handler
  useEffect(() => {
    const handleResize = () => renderCanvas();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [renderCanvas]);

  // Mouse Move / Hover Detection
  const handleMouseMove = (e) => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const rect = canvas.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const clientY = e.clientY - rect.top;

    const width = container.clientWidth;
    const height = container.clientHeight;
    const padX = Math.max(42, width * 0.07);
    const padY = Math.max(46, height * 0.09);
    const venueW = width - padX * 2;
    const venueH = height - padY * 2;

    const normX = Math.max(0, Math.min(1, (clientX - padX) / venueW));
    const normY = Math.max(0, Math.min(1, (clientY - padY) / venueH));
    setMouseNorm({ x: normX, y: normY });

    // Find nearest point within click threshold
    let nearest = null;
    let minDist = 32; // pixel threshold

    filteredPoints.forEach((pt) => {
      const px = padX + pt.x * venueW;
      const py = padY + pt.y * venueH;
      const dist = Math.hypot(clientX - px, clientY - py);
      if (dist < minDist) {
        minDist = dist;
        nearest = pt;
      }
    });

    setHoveredPoint(nearest);
    if (nearest) {
      setTooltipPos({ x: clientX, y: clientY });
    } else {
      setTooltipPos(null);
    }
  };

  const handleClick = () => {
    if (hoveredPoint && onSelectPoint) {
      onSelectPoint(selectedPoint?.id === hoveredPoint.id ? null : hoveredPoint);
    } else if (!hoveredPoint && onSelectPoint) {
      onSelectPoint(null);
    }
  };

  return (
    <div
      ref={containerRef}
      className="venue-2d-container"
      onMouseMove={handleMouseMove}
      onMouseLeave={() => {
        setHoveredPoint(null);
        setTooltipPos(null);
        setMouseNorm(null);
      }}
      onClick={handleClick}
      role="region"
      aria-label="2D Camera-Derived Venue Crowd Heatmap"
    >
      <canvas ref={canvasRef} className="venue-2d-canvas" />

      {/* Floating HUD status in top right */}
      <div className="venue-2d-hud-badge">
        <span className="venue-hud-dot" />
        <span>CAMERA-DERIVED VENUE MODEL</span>
      </div>

      {/* Interactive Tooltip Card */}
      {hoveredPoint && tooltipPos && (
        <div
          className="venue-2d-tooltip animate-fade-in"
          style={{
            left: Math.min(tooltipPos.x + 12, (containerRef.current?.clientWidth || 400) - 220),
            top: Math.max(12, tooltipPos.y - 80),
          }}
        >
          <div className="venue-tooltip-header">
            <strong>{hoveredPoint.name}</strong>
            <span
              className="venue-tooltip-risk-tag"
              style={{ background: RISK_PALETTE[hoveredPoint.riskLevel]?.hex || '#22c55e' }}
            >
              {isManager ? hoveredPoint.riskLevel : hoveredPoint.crowdStatus}
            </span>
          </div>
          <div className="venue-tooltip-body">
            <div className="venue-tooltip-metric">
              <span>Spatial Region:</span>
              <strong>{hoveredPoint.spatialCoord || `X ${hoveredPoint.x.toFixed(2)} / Y ${hoveredPoint.y.toFixed(2)}`}</strong>
            </div>
            <div className="venue-tooltip-metric">
              <span>Crowd Density:</span>
              <strong>{hoveredPoint.density} people</strong>
            </div>
            {isManager && (
              <div className="venue-tooltip-metric">
                <span>Risk Score:</span>
                <strong>{hoveredPoint.riskScore} / 100</strong>
              </div>
            )}
            <p className="venue-tooltip-action">{hoveredPoint.action}</p>
          </div>
        </div>
      )}
    </div>
  );
}
