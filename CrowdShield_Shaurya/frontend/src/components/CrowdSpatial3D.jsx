/**
 * CrowdSpatial3D — Reusable Interactive 3D Spatial Crowd Model for CrowdShield.
 *
 * Visualizes the currently selected camera's crowd density across a normalized 3D ground plane.
 * Each of the 3x3 optical zones is represented as an interactive vertical spatial column
 * whose height and color dynamically correspond to real-time crowd density and risk level.
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import RiskBadge from './RiskBadge';
import { trendIcon } from '../utils';
import { getCameraSpatialConfig } from '../config/cameraSpatialConfig';
import './CrowdSpatial3D.css';

// Color palette mapping to CrowdShield design system
const RISK_COLORS = {
  LOW:      0x22c55e, // var(--risk-low)
  MEDIUM:   0xf59e0b, // var(--risk-medium)
  HIGH:     0xf97316, // var(--risk-high)
  CRITICAL: 0xef4444, // var(--risk-critical)
};

const RISK_HEX = {
  LOW:      '#22c55e',
  MEDIUM:   '#f59e0b',
  HIGH:     '#f97316',
  CRITICAL: '#ef4444',
};

/** Creates a high-DPI canvas texture for the top face of each zone column */
function createZoneTopTexture(zoneLabel, density, riskLevel, trend) {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 192;
  const ctx = canvas.getContext('2d');

  // Background
  const hex = RISK_HEX[riskLevel] || '#22c55e';
  ctx.fillStyle = '#0f172a';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Border
  ctx.strokeStyle = hex;
  ctx.lineWidth = 8;
  ctx.strokeRect(4, 4, canvas.width - 8, canvas.height - 8);

  // Header Zone Label
  ctx.fillStyle = hex;
  ctx.font = 'bold 36px "Inter", sans-serif';
  ctx.fillText(zoneLabel, 18, 48);

  // Trend icon
  ctx.fillStyle = '#94a3b8';
  ctx.font = '30px "Inter", sans-serif';
  ctx.fillText(trendIcon(trend), canvas.width - 44, 48);

  // Density Count (Large)
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 76px "JetBrains Mono", monospace';
  ctx.fillText(String(density ?? 0), 18, 136);

  // People subtitle
  ctx.fillStyle = '#94a3b8';
  ctx.font = '600 24px "Inter", sans-serif';
  ctx.fillText('PEOPLE', 18, 172);

  // Risk Level badge
  ctx.fillStyle = hex;
  ctx.font = 'bold 22px "Inter", sans-serif';
  ctx.fillText(riskLevel, canvas.width - 110, 172);

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
}

export default function CrowdSpatial3D({
  cameraId = 'cam1',
  cameraName = '',
  zones = [],
  prevention = null,
  selectedZone = null,
  onZoneClick = null,
  className = '',
}) {
  const containerRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const rendererRef = useRef(null);
  const controlsRef = useRef(null);
  const zoneGroupRef = useRef(null);
  const animFrameRef = useRef(null);
  const raycasterRef = useRef(new THREE.Raycaster());
  const mouseRef = useRef(new THREE.Vector2());

  const [hoveredZone, setHoveredZone] = useState(null);
  const [activeZoneDetail, setActiveZoneDetail] = useState(null);

  const camConfig = useMemo(() => getCameraSpatialConfig(cameraId), [cameraId]);
  const displayName = cameraName || camConfig.name;

  const totalPeople = prevention?.total_people ?? zones.reduce((sum, z) => sum + (z.density || 0), 0);
  const highestRiskLevel = prevention?.highest_risk_level || 'LOW';

  // ── 1. Setup Three.js Scene, Camera, Lights & Ground Plane ──────
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth || 600;
    const height = container.clientHeight || 420;

    // Camera spatial dimensions (normalized)
    const planeW = camConfig?.planeSize?.[0] || camConfig?.planeWidth || 14;
    const planeD = camConfig?.planeSize?.[1] || camConfig?.planeDepth || 10;
    const [defX, defY, defZ] = Array.isArray(camConfig?.defaultCameraPos) ? camConfig.defaultCameraPos : [0, 8.5, 11];

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0c10);
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(48, width / height, 0.1, 100);
    camera.position.set(defX, defY, defZ);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Orbit Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.maxPolarAngle = Math.PI / 2 - 0.04; // Never go below ground
    controls.minPolarAngle = 0.15;
    controls.minDistance = 5;
    controls.maxDistance = 22;
    controls.target.set(0, 0, 0);
    controlsRef.current = controls;

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.85);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 0.9);
    dirLight.position.set(6, 14, 8);
    scene.add(dirLight);

    const softFill = new THREE.DirectionalLight(0x38bdf8, 0.35);
    softFill.position.set(-6, 8, -6);
    scene.add(softFill);

    // ── Ground Plane ─────────────────────────────────────────────
    const groundGeo = new THREE.PlaneGeometry(planeW, planeD);
    const groundMat = new THREE.MeshStandardMaterial({
      color: 0x111622,
      roughness: 0.85,
      metalness: 0.1,
    });
    const groundMesh = new THREE.Mesh(groundGeo, groundMat);
    groundMesh.rotation.x = -Math.PI / 2;
    groundMesh.position.y = -0.01;
    scene.add(groundMesh);

    // Grid helper overlay on ground
    const gridHelper = new THREE.GridHelper(planeW, 12, 0x4f46e5, 0x1e293b);
    gridHelper.position.y = 0.005;
    scene.add(gridHelper);

    // Boundary frame for camera FOV area
    const edgesGeo = new THREE.EdgesGeometry(new THREE.BoxGeometry(planeW, 0.04, planeD));
    const edgesMat = new THREE.LineBasicMaterial({ color: 0x3b82f6, linewidth: 2 });
    const edgesMesh = new THREE.LineSegments(edgesGeo, edgesMat);
    edgesMesh.position.y = 0.01;
    scene.add(edgesMesh);

    // Camera Origin Observer Icon / Frustum Apex indicator (near Z bottom edge)
    const observerGroup = new THREE.Group();
    observerGroup.position.set(0, 0.15, planeD / 2 + 0.6);

    const coneGeo = new THREE.ConeGeometry(0.35, 0.7, 4);
    coneGeo.rotateX(Math.PI / 2);
    const coneMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8 });
    const coneMesh = new THREE.Mesh(coneGeo, coneMat);
    observerGroup.add(coneMesh);

    const camLabelLineGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-planeW / 2, 0, -0.6),
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(planeW / 2, 0, -0.6),
    ]);
    const camLineMat = new THREE.LineDashedMaterial({ color: 0x38bdf8, dashSize: 0.3, gapSize: 0.2 });
    const camLines = new THREE.Line(camLabelLineGeo, camLineMat);
    camLines.computeLineDistances();
    observerGroup.add(camLines);

    scene.add(observerGroup);

    // Group to hold dynamic zone meshes
    const zoneGroup = new THREE.Group();
    scene.add(zoneGroup);
    zoneGroupRef.current = zoneGroup;

    // Render loop
    const animate = () => {
      animFrameRef.current = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // Resize observer
    const resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width: w, height: h } = entry.contentRect;
        if (w > 0 && h > 0) {
          camera.aspect = w / h;
          camera.updateProjectionMatrix();
          renderer.setSize(w, h);
        }
      }
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      controls.dispose();
      renderer.dispose();
      groundGeo.dispose();
      groundMat.dispose();
      edgesGeo.dispose();
      edgesMat.dispose();
      coneGeo.dispose();
      coneMat.dispose();
      camLabelLineGeo.dispose();
      camLineMat.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [camConfig]);

  // ── 2. Build 3×3 Dynamic Vertical Spatial Columns ────────────
  useEffect(() => {
    const zoneGroup = zoneGroupRef.current;
    if (!zoneGroup) return;

    // Clear previous zone meshes and textures
    while (zoneGroup.children.length > 0) {
      const child = zoneGroup.children[0];
      zoneGroup.remove(child);
      if (child.geometry) child.geometry.dispose();
      if (Array.isArray(child.material)) {
        child.material.forEach(m => {
          if (m.map) m.map.dispose();
          m.dispose();
        });
      } else if (child.material) {
        if (child.material.map) child.material.map.dispose();
        child.material.dispose();
      }
    }

    if (!zones || zones.length === 0) return;

    const zoneMap = new Map();
    zones.forEach(z => zoneMap.set(z.zone, z));

    // Spatial layout: 3 rows (Z) x 3 cols (X)
    const planeW = camConfig?.planeSize?.[0] || camConfig?.planeWidth || 14;
    const planeD = camConfig?.planeSize?.[1] || camConfig?.planeDepth || 10;
    const colWidth = (planeW - 0.6) / 3;  // ~3.8
    const rowDepth = (planeD - 0.6) / 3;  // ~2.46
    const blockW = colWidth * 0.9;
    const blockD = rowDepth * 0.9;

    const xOffsets = [-colWidth, 0, colWidth];
    // Z1-Z3 = Row 0 (far, -rowDepth), Z4-Z6 = Row 1 (center, 0), Z7-Z9 = Row 2 (near, +rowDepth)
    const zOffsets = [-rowDepth, 0, rowDepth];

    for (let row = 0; row < 3; row++) {
      for (let col = 0; col < 3; col++) {
        const zoneIdx = row * 3 + col + 1;
        const zoneId = `Z${zoneIdx}`;
        const zoneData = zoneMap.get(zoneId) || { zone: zoneId, density: 0, risk_level: 'LOW', trend: 'STABLE' };

        const density = Number(zoneData.density || 0);
        const level = zoneData.risk_level || (density >= 30 ? 'CRITICAL' : density >= 15 ? 'HIGH' : density >= 5 ? 'MEDIUM' : 'LOW');
        const trend = zoneData.trend || 'STABLE';

        // Vertical height scaled by crowd density
        const height = Math.max(0.25, Math.min(0.25 + density * 0.14, 3.8));
        const posX = xOffsets[col];
        const posZ = zOffsets[row];
        const posY = height / 2;

        const isSelected = selectedZone?.zone === zoneId || selectedZone === zoneId || activeZoneDetail?.zone === zoneId;
        const colorHex = RISK_COLORS[level] || 0x22c55e;

        const boxGeo = new THREE.BoxGeometry(blockW, height, blockD);

        // Materials: top face has dynamic canvas texture with zone label & density
        const topTexture = createZoneTopTexture(zoneId, density, level, trend);
        const topMat = new THREE.MeshBasicMaterial({ map: topTexture });

        const sideMat = new THREE.MeshStandardMaterial({
          color: colorHex,
          roughness: 0.25,
          metalness: 0.1,
          transparent: true,
          opacity: isSelected ? 0.95 : 0.82,
        });

        // Box faces: [right, left, top, bottom, front, back]
        const materials = [sideMat, sideMat, topMat, sideMat, sideMat, sideMat];
        const boxMesh = new THREE.Mesh(boxGeo, materials);
        boxMesh.position.set(posX, posY, posZ);
        boxMesh.userData = { zoneData, zoneId };

        // Wireframe edges on columns for technical aesthetic
        const boxEdgesGeo = new THREE.EdgesGeometry(boxGeo);
        const boxEdgesMat = new THREE.LineBasicMaterial({
          color: isSelected ? 0xffffff : colorHex,
          transparent: true,
          opacity: isSelected ? 0.9 : 0.45,
        });
        const boxEdges = new THREE.LineSegments(boxEdgesGeo, boxEdgesMat);
        boxMesh.add(boxEdges);

        // Ground base ring / footprint marker
        const ringGeo = new THREE.RingGeometry(blockW * 0.42, blockW * 0.46, 16);
        ringGeo.rotateX(-Math.PI / 2);
        const ringMat = new THREE.MeshBasicMaterial({
          color: colorHex,
          side: THREE.DoubleSide,
          transparent: true,
          opacity: 0.35,
        });
        const ringMesh = new THREE.Mesh(ringGeo, ringMat);
        ringMesh.position.set(0, -posY + 0.002, 0);
        boxMesh.add(ringMesh);

        zoneGroup.add(boxMesh);
      }
    }
  }, [zones, selectedZone, activeZoneDetail, camConfig]);

  // ── 3. Interactive Raycasting on Hover & Click ────────────────
  const handlePointerDown = useCallback((e) => {
    const container = containerRef.current;
    const camera = cameraRef.current;
    const zoneGroup = zoneGroupRef.current;
    if (!container || !camera || !zoneGroup) return;

    const rect = container.getBoundingClientRect();
    mouseRef.current.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouseRef.current.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    raycasterRef.current.setFromCamera(mouseRef.current, camera);
    const intersects = raycasterRef.current.intersectObjects(zoneGroup.children, true);

    if (intersects.length > 0) {
      // Find parent box mesh
      let target = intersects[0].object;
      while (target && !target.userData?.zoneData && target.parent) {
        target = target.parent;
      }
      if (target?.userData?.zoneData) {
        const clickedData = target.userData.zoneData;
        setActiveZoneDetail(clickedData);
        if (onZoneClick) onZoneClick(clickedData);
      }
    }
  }, [onZoneClick]);

  const handlePointerMove = useCallback((e) => {
    const container = containerRef.current;
    const camera = cameraRef.current;
    const zoneGroup = zoneGroupRef.current;
    if (!container || !camera || !zoneGroup) return;

    const rect = container.getBoundingClientRect();
    mouseRef.current.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouseRef.current.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    raycasterRef.current.setFromCamera(mouseRef.current, camera);
    const intersects = raycasterRef.current.intersectObjects(zoneGroup.children, true);

    if (intersects.length > 0) {
      let target = intersects[0].object;
      while (target && !target.userData?.zoneData && target.parent) {
        target = target.parent;
      }
      if (target?.userData?.zoneData) {
        container.style.cursor = 'pointer';
        setHoveredZone(target.userData.zoneData);
        return;
      }
    }
    container.style.cursor = 'grab';
    setHoveredZone(null);
  }, []);

  // ── 4. Camera Reset Function ──────────────────────────────────
  const handleResetCamera = useCallback(() => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls) return;

    const [defX, defY, defZ] = Array.isArray(camConfig?.defaultCameraPos) ? camConfig.defaultCameraPos : [0, 8.5, 11];
    camera.position.set(defX, defY, defZ);
    controls.target.set(0, 0, 0);
    controls.update();
  }, [camConfig]);

  const activeThreat = prevention?.threats?.find(t => t.zone === (activeZoneDetail?.zone || selectedZone?.zone));

  return (
    <div className={`crowd-spatial-3d card ${className}`}>
      {/* ── HUD Header Overlay ────────────────────────────────── */}
      <div className="crowd-spatial-3d__hud-header">
        <div className="crowd-spatial-3d__cam-badge" title="Active Camera Spatial View">
          <span className={`crowd-spatial-3d__cam-dot ${highestRiskLevel === 'CRITICAL' || highestRiskLevel === 'HIGH' ? 'crowd-spatial-3d__cam-dot--alert' : ''}`} />
          <span>{displayName.toUpperCase()} — 3D SPATIAL MODEL</span>
          <RiskBadge level={highestRiskLevel} size="sm" />
          <span style={{ fontSize: '0.75rem', opacity: 0.85, color: 'var(--text-secondary)', marginLeft: 4 }}>
            • {totalPeople} People
          </span>
          {hoveredZone && (
            <span style={{ fontSize: '0.72rem', color: 'var(--accent)', marginLeft: 6, padding: '1px 6px', background: 'var(--bg-card)', borderRadius: 4, border: '1px solid rgba(255,255,255,0.08)' }}>
              Hovering: {hoveredZone.zone} ({hoveredZone.density || 0} pax)
            </span>
          )}
        </div>

        <div className="crowd-spatial-3d__hud-controls">
          <button
            className="crowd-spatial-3d__reset-btn"
            onClick={handleResetCamera}
            title="Reset to optimal 3D isometric angle"
          >
            🔄 Reset View
          </button>
        </div>
      </div>

      {/* ── Selected Zone Detail Floating Card ────────────────── */}
      {(activeZoneDetail || selectedZone) && (
        <div className="crowd-spatial-3d__zone-popup">
          <div className="crowd-spatial-3d__zone-popup-header">
            <span className="crowd-spatial-3d__zone-popup-title">
              📍 {(activeZoneDetail || selectedZone).zone}
            </span>
            <RiskBadge level={(activeZoneDetail || selectedZone).risk_level} size="sm" />
            <button
              className="crowd-spatial-3d__zone-popup-close"
              onClick={() => { setActiveZoneDetail(null); }}
              aria-label="Close"
            >
              ✕
            </button>
          </div>
          <div className="crowd-spatial-3d__zone-popup-stats">
            <span>Density: <strong>{(activeZoneDetail || selectedZone).density ?? 0}</strong></span>
            <span>Trend: <strong>{trendIcon((activeZoneDetail || selectedZone).trend)} {(activeZoneDetail || selectedZone).trend ?? 'STABLE'}</strong></span>
          </div>
          {((activeZoneDetail || selectedZone).risk_cause || activeThreat?.risk_cause) && (
            <p style={{ margin: '6px 0 0', fontSize: '0.72rem', color: 'var(--risk-medium)' }}>
              ⚠ {(activeZoneDetail || selectedZone).risk_cause || activeThreat?.risk_cause}
            </p>
          )}
        </div>
      )}

      {/* ── Three.js Canvas Container ─────────────────────────── */}
      <div
        ref={containerRef}
        className="crowd-spatial-3d__canvas-container"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
      />

      {/* ── Empty State / Loading Overlay ─────────────────────── */}
      {(!zones || zones.length === 0) && (
        <div className="crowd-spatial-3d__empty-overlay">
          <span className="crowd-spatial-3d__empty-icon">📡</span>
          <span className="crowd-spatial-3d__empty-title">Awaiting Camera Spatial Data</span>
          <span className="crowd-spatial-3d__empty-sub">
            Spatial model for {displayName} will render as soon as crowd analytics feed is connected.
          </span>
        </div>
      )}

      {/* ── Bottom Legend Overlay ─────────────────────────────── */}
      <div className="crowd-spatial-3d__legend">
        <span className="crowd-spatial-3d__legend-title">3D Crowd Density</span>
        <div className="crowd-spatial-3d__legend-items">
          <div className="crowd-spatial-3d__legend-item">
            <span className="crowd-spatial-3d__legend-color" style={{ background: '#22c55e' }} />
            <span>Low (&lt; 5)</span>
          </div>
          <div className="crowd-spatial-3d__legend-item">
            <span className="crowd-spatial-3d__legend-color" style={{ background: '#f59e0b' }} />
            <span>Moderate (5–15)</span>
          </div>
          <div className="crowd-spatial-3d__legend-item">
            <span className="crowd-spatial-3d__legend-color" style={{ background: '#f97316' }} />
            <span>High (15–30)</span>
          </div>
          <div className="crowd-spatial-3d__legend-item">
            <span className="crowd-spatial-3d__legend-color" style={{ background: '#ef4444' }} />
            <span>Critical (30+)</span>
          </div>
        </div>
      </div>

      {/* ── Bottom Navigation Instructions ────────────────────── */}
      <div className="crowd-spatial-3d__nav-help">
        <span>🖱️ Drag to rotate</span>
        <span>•</span>
        <span>Scroll to zoom</span>
        <span>•</span>
        <span>Right-click to pan</span>
      </div>
    </div>
  );
}
