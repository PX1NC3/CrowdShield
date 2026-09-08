/**
 * VenueHeatmap3D.jsx
 * 
 * Camera-Derived 3D Venue Crowd Intelligence Surface.
 * Renders a continuous raised terrain surface corresponding 100% with the 2D venue heatmap.
 * 
 * Visualization Encodings:
 *   HEIGHT = Crowd Density (Nonlinear relative amplification, peaks at crowd clusters)
 *   COLOUR = Risk Level (Dark tactical ground -> Emerald Low -> Amber Medium -> Orange High -> Red Critical)
 * 
 * Full Orbit / Pan / Zoom interaction with Three.js OrbitControls.
 */

import { useRef, useEffect, useState, useMemo } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import {
  evaluateFieldAt,
  densityToHeight,
  getTerrainVertexRgb,
  interpolateRiskRgb,
  RISK_PALETTE,
  BASE_GROUND_RGB,
} from '../utils/venueHeatmapModel';
import './VenueHeatmap3D.css';

const PLANE_WIDTH = 34;
const PLANE_DEPTH = 26;
const GRID_RES_X = 100;
const GRID_RES_Y = 80;

export default function VenueHeatmap3D({
  points = [],
  detections = [],
  cameraInfo = null,
  selectedPoint = null,
  onSelectPoint = null,
  isManager = true,
  filter = 'ALL',
}) {
  const containerRef = useRef(null);
  const canvasMountRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const rendererRef = useRef(null);
  const controlsRef = useRef(null);
  const terrainMeshRef = useRef(null);
  const wireframeMeshRef = useRef(null);
  const beaconsGroupRef = useRef(null);
  const animIdRef = useRef(null);
  const raycasterRef = useRef(new THREE.Raycaster());
  const mouseRef = useRef(new THREE.Vector2());

  // Buffer arrays for smooth fluid lerping between frames
  const targetYRef = useRef(null);
  const targetColorRef = useRef(null);

  const [autoRotate, setAutoRotate] = useState(false);
  const [heightScale, setHeightScale] = useState(1.2);

  // Filtered points
  const filteredPoints = useMemo(() => {
    return points.filter(pt => {
      if (filter === 'HIGH') return pt.riskLevel === 'HIGH' || pt.riskLevel === 'CRITICAL';
      if (filter === 'CRITICAL') return pt.riskLevel === 'CRITICAL';
      if (filter === 'MODERATE') return pt.riskLevel === 'MEDIUM' || pt.crowdStatus === 'Moderate' || pt.crowdStatus === 'Crowded';
      if (filter === 'CROWDED') return pt.crowdStatus === 'Crowded' || pt.riskLevel === 'CRITICAL';
      return true;
    });
  }, [points, filter]);

  // ── 1. Setup Three.js Scene, Camera, Lights, Terrain & Controls ─
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth || 800;
    const height = container.clientHeight || 520;

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x090d16);
    scene.fog = new THREE.FogExp2(0x090d16, 0.012);
    sceneRef.current = scene;

    // Camera (Elevated Isometric Perspective for clear relief observation)
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.5, 200);
    camera.position.set(18, 22, 28);
    camera.lookAt(0, 1.5, 0);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    rendererRef.current = renderer;

    const canvasMount = canvasMountRef.current;
    if (canvasMount) {
      canvasMount.innerHTML = '';
      canvasMount.appendChild(renderer.domElement);
    }

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.maxPolarAngle = Math.PI / 2 - 0.04; // Do not go below floor
    controls.minDistance = 12;
    controls.maxDistance = 68;
    controls.target.set(0, 1.5, 0);
    controlsRef.current = controls;

    // Lighting (Directional shadows emphasize relief on hill slopes)
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.65);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xffffff, 1.25);
    dirLight1.position.set(22, 32, 20);
    dirLight1.castShadow = true;
    dirLight1.shadow.mapSize.width = 1024;
    dirLight1.shadow.mapSize.height = 1024;
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x38bdf8, 0.5);
    dirLight2.position.set(-22, 16, -18);
    scene.add(dirLight2);

    // Tactical Base Pedestal under the visible ground
    const baseGeo = new THREE.BoxGeometry(PLANE_WIDTH + 1.2, 0.7, PLANE_DEPTH + 1.2);
    const baseMat = new THREE.MeshStandardMaterial({
      color: 0x0f172a,
      roughness: 0.85,
      metalness: 0.15,
    });
    const baseMesh = new THREE.Mesh(baseGeo, baseMat);
    baseMesh.position.y = -0.38;
    scene.add(baseMesh);

    // Subtle Tactical Grid Floor on base
    const gridHelper = new THREE.GridHelper(Math.max(PLANE_WIDTH, PLANE_DEPTH), 28, 0x38bdf8, 0x1e293b);
    gridHelper.position.y = 0.01;
    scene.add(gridHelper);

    // Beacons Group
    const beaconsGroup = new THREE.Group();
    scene.add(beaconsGroup);
    beaconsGroupRef.current = beaconsGroup;

    // ── Create Continuous Terrain Surface Mesh ────────────────
    const terrainGeo = new THREE.PlaneGeometry(PLANE_WIDTH, PLANE_DEPTH, GRID_RES_X, GRID_RES_Y);
    // Rotate to horizontal XZ plane
    terrainGeo.rotateX(-Math.PI / 2);

    // Prepare vertex colors attribute initialized to sleek dark tactical ground
    const count = terrainGeo.attributes.position.count;
    const colors = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      colors[i * 3]     = BASE_GROUND_RGB[0] / 255;
      colors[i * 3 + 1] = BASE_GROUND_RGB[1] / 255;
      colors[i * 3 + 2] = BASE_GROUND_RGB[2] / 255;
    }
    terrainGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    // Allocate smooth lerp target arrays
    targetYRef.current = new Float32Array(count);
    targetColorRef.current = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      targetYRef.current[i] = 0.08;
      targetColorRef.current[i * 3]     = BASE_GROUND_RGB[0] / 255;
      targetColorRef.current[i * 3 + 1] = BASE_GROUND_RGB[1] / 255;
      targetColorRef.current[i * 3 + 2] = BASE_GROUND_RGB[2] / 255;
    }

    const terrainMat = new THREE.MeshStandardMaterial({
      vertexColors: true,
      roughness: 0.42,
      metalness: 0.16,
      flatShading: false,
      side: THREE.DoubleSide,
    });

    const terrainMesh = new THREE.Mesh(terrainGeo, terrainMat);
    terrainMesh.castShadow = true;
    terrainMesh.receiveShadow = true;
    scene.add(terrainMesh);
    terrainMeshRef.current = terrainMesh;

    // Subtle wireframe overlay for cyber-topographic surface aesthetic
    const wireframeMat = new THREE.MeshBasicMaterial({
      color: 0x38bdf8,
      wireframe: true,
      transparent: true,
      opacity: 0.035, // Very subtle, does not clutter the relief
    });
    const wireframeMesh = new THREE.Mesh(terrainGeo, wireframeMat);
    wireframeMesh.position.y = 0.015;
    scene.add(wireframeMesh);
    wireframeMeshRef.current = wireframeMesh;

    // Animation Render Loop with Fluid Vertex Lerping
    let animationActive = true;
    const animate = () => {
      if (!animationActive) return;
      controls.update();

      // Fluid vertex lerp toward target elevations & risk colors
      if (terrainMeshRef.current && targetYRef.current && targetColorRef.current) {
        const geo = terrainMeshRef.current.geometry;
        const posAttr = geo.attributes.position;
        const colAttr = geo.attributes.color;
        const pos = posAttr.array;
        const col = colAttr.array;
        const targetY = targetYRef.current;
        const targetC = targetColorRef.current;
        const vCount = posAttr.count;
        let needsUpdate = false;

        for (let i = 0; i < vCount; i++) {
          const curY = pos[i * 3 + 1];
          const tgtY = targetY[i];
          if (Math.abs(curY - tgtY) > 0.003) {
            pos[i * 3 + 1] = curY + (tgtY - curY) * 0.14;
            needsUpdate = true;
          }

          const cIdx = i * 3;
          if (
            Math.abs(col[cIdx]     - targetC[cIdx])     > 0.003 ||
            Math.abs(col[cIdx + 1] - targetC[cIdx + 1]) > 0.003 ||
            Math.abs(col[cIdx + 2] - targetC[cIdx + 2]) > 0.003
          ) {
            col[cIdx]     += (targetC[cIdx]     - col[cIdx])     * 0.14;
            col[cIdx + 1] += (targetC[cIdx + 1] - col[cIdx + 1]) * 0.14;
            col[cIdx + 2] += (targetC[cIdx + 2] - col[cIdx + 2]) * 0.14;
            needsUpdate = true;
          }
        }

        if (needsUpdate) {
          posAttr.needsUpdate = true;
          colAttr.needsUpdate = true;
          geo.computeVertexNormals();
        }
      }

      renderer.render(scene, camera);
      animIdRef.current = requestAnimationFrame(animate);
    };
    animate();

    // Resize Observer
    const resizeObserver = new ResizeObserver((entries) => {
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
      animationActive = false;
      if (animIdRef.current) cancelAnimationFrame(animIdRef.current);
      resizeObserver.disconnect();
      controls.dispose();
      renderer.dispose();
      terrainGeo.dispose();
      terrainMat.dispose();
      wireframeMat.dispose();
      baseGeo.dispose();
      baseMat.dispose();
    };
  }, []);

  // Update autoRotate on controls
  useEffect(() => {
    if (controlsRef.current) {
      controlsRef.current.autoRotate = autoRotate;
      controlsRef.current.autoRotateSpeed = 1.2;
    }
  }, [autoRotate]);

  // ── 2. Update Continuous 3D Surface Targets from Heatmap Points ──
  useEffect(() => {
    const terrainMesh = terrainMeshRef.current;
    if (!terrainMesh) return;

    const geo = terrainMesh.geometry;
    const posAttr = geo.attributes.position;
    const count = posAttr.count;

    if (!targetYRef.current || targetYRef.current.length !== count) {
      targetYRef.current = new Float32Array(count);
      targetColorRef.current = new Float32Array(count * 3);
    }

    const targetY = targetYRef.current;
    const targetC = targetColorRef.current;

    // Dynamic relative amplification:
    // Determine max hotspot density in the active set so small clusters (e.g. 2-8 pax)
    // rise prominently rather than being compressed into a flat plane.
    const maxPtDensity = Math.max(1, ...filteredPoints.map(p => p.density || 1));
    const maxHeight = 5.2 * heightScale;
    const minHeight = 0.08;

    for (let i = 0; i < count; i++) {
      const vx = posAttr.getX(i);
      const vz = posAttr.getZ(i);

      // Normalize vx and vz to venue space [0, 1] x [0, 1]
      // Matches 2D canvas coordinates identically
      const nx = (vx + PLANE_WIDTH / 2) / PLANE_WIDTH;
      const ny = (vz + PLANE_DEPTH / 2) / PLANE_DEPTH;

      // Evaluate shared continuous field at (nx, ny)
      const { density, riskScore } = evaluateFieldAt(nx, ny, filteredPoints, 0.125);

      // Height = Crowd Density with nonlinear amplification
      const h = densityToHeight(density, maxPtDensity, maxHeight, minHeight);
      targetY[i] = h;

      // Normalized density for color transition
      const densityNorm = Math.min(1.0, density / Math.max(2.5, maxPtDensity));
      const [r, g, b] = getTerrainVertexRgb(riskScore, densityNorm);

      targetC[i * 3]     = r;
      targetC[i * 3 + 1] = g;
      targetC[i * 3 + 2] = b;
    }

    // ── 3. Update 3D Floating Beacons at Hotspot Peaks ────────
    const beaconsGroup = beaconsGroupRef.current;
    if (!beaconsGroup) return;

    // Clear old beacon children
    while (beaconsGroup.children.length > 0) {
      const obj = beaconsGroup.children[0];
      beaconsGroup.remove(obj);
      if (obj.geometry) obj.geometry.dispose();
      if (obj.material) {
        if (Array.isArray(obj.material)) obj.material.forEach(m => m.dispose());
        else obj.material.dispose();
      }
    }

    // Add holographic beacon column for each hotspot
    filteredPoints.forEach((pt) => {
      const bx = (pt.x - 0.5) * PLANE_WIDTH;
      const bz = (pt.y - 0.5) * PLANE_DEPTH;

      // Exact peak height of the terrain at this hotspot
      const peakHeight = densityToHeight(pt.density, maxPtDensity, maxHeight, minHeight);
      const [r, g, b] = interpolateRiskRgb(pt.riskScore);
      const hexColor = (r << 16) | (g << 8) | b;

      // Vertical holographic light column
      const cylinderGeo = new THREE.CylinderGeometry(0.16, 0.16, peakHeight + 1.0, 16);
      const cylinderMat = new THREE.MeshStandardMaterial({
        color: hexColor,
        emissive: hexColor,
        emissiveIntensity: 0.65,
        transparent: true,
        opacity: 0.75,
        roughness: 0.2,
      });
      const cylinderMesh = new THREE.Mesh(cylinderGeo, cylinderMat);
      cylinderMesh.position.set(bx, (peakHeight + 1.0) / 2, bz);
      cylinderMesh.userData = { point: pt };
      beaconsGroup.add(cylinderMesh);

      // Glowing peak orb
      const orbGeo = new THREE.SphereGeometry(0.42, 16, 16);
      const orbMat = new THREE.MeshStandardMaterial({
        color: 0xffffff,
        emissive: hexColor,
        emissiveIntensity: 1.0,
      });
      const orbMesh = new THREE.Mesh(orbGeo, orbMat);
      orbMesh.position.set(bx, peakHeight + 1.0, bz);
      orbMesh.userData = { point: pt };
      beaconsGroup.add(orbMesh);

      // Beacon Ground Ring
      const ringGeo = new THREE.RingGeometry(0.55, 0.85, 24);
      ringGeo.rotateX(-Math.PI / 2);
      const ringMat = new THREE.MeshBasicMaterial({
        color: hexColor,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.8,
      });
      const ringMesh = new THREE.Mesh(ringGeo, ringMat);
      ringMesh.position.set(bx, 0.05, bz);
      beaconsGroup.add(ringMesh);
    });
  }, [filteredPoints, heightScale]);

  // Camera View Presets
  const handleResetCamera = () => {
    if (controlsRef.current && cameraRef.current) {
      cameraRef.current.position.set(18, 22, 28);
      controlsRef.current.target.set(0, 1.5, 0);
      controlsRef.current.update();
    }
  };

  const handleTopDownView = () => {
    if (controlsRef.current && cameraRef.current) {
      cameraRef.current.position.set(0, 38, 0.01);
      controlsRef.current.target.set(0, 0, 0);
      controlsRef.current.update();
    }
  };

  const handleSideView = () => {
    if (controlsRef.current && cameraRef.current) {
      cameraRef.current.position.set(0, 6, 32);
      controlsRef.current.target.set(0, 1.5, 0);
      controlsRef.current.update();
    }
  };

  const handleCanvasClick = (e) => {
    if (!rendererRef.current || !cameraRef.current || !beaconsGroupRef.current) return;
    const rect = rendererRef.current.domElement.getBoundingClientRect();
    mouseRef.current.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouseRef.current.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    raycasterRef.current.setFromCamera(mouseRef.current, cameraRef.current);
    const intersects = raycasterRef.current.intersectObjects(beaconsGroupRef.current.children, true);

    if (intersects.length > 0) {
      let obj = intersects[0].object;
      while (obj && !obj.userData?.point && obj.parent) {
        obj = obj.parent;
      }
      if (obj?.userData?.point && onSelectPoint) {
        onSelectPoint(selectedPoint?.id === obj.userData.point.id ? null : obj.userData.point);
      }
    }
  };

  return (
    <div className="venue-3d-container" ref={containerRef} role="region" aria-label="3D Camera-Derived Venue Crowd Surface">
      <div className="venue-3d-mount" ref={canvasMountRef} onClick={handleCanvasClick} />

      {/* Top HUD Overlay */}
      <div className="venue-3d-hud-header">
        <div className="venue-3d-tag">
          <span className="venue-hud-dot" />
          <span>CAMERA-DERIVED VENUE MODEL · 3D SURFACE</span>
        </div>
        <div className="venue-3d-mapping-legend">
          <span>SPATIAL DATA: <strong>REAL DETECTIONS</strong></span>
          <span className="legend-divider">|</span>
          <span>HEIGHT = <strong>CROWD DENSITY</strong></span>
          <span className="legend-divider">|</span>
          <span>COLOUR = <strong>RISK LEVEL</strong></span>
        </div>
      </div>

      {/* Interactive Controls Overlay Toolbar */}
      <div className="venue-3d-toolbar">
        <button
          type="button"
          className="btn btn-sm btn-ghost venue-3d-btn"
          onClick={handleResetCamera}
          title="Reset to Elevated Isometric 3D Perspective"
        >
          <span>📐</span> Isometric
        </button>
        <button
          type="button"
          className="btn btn-sm btn-ghost venue-3d-btn"
          onClick={handleTopDownView}
          title="Direct Top-Down View (Corresponds 1:1 with 2D)"
        >
          <span>🗺</span> Top View
        </button>
        <button
          type="button"
          className="btn btn-sm btn-ghost venue-3d-btn"
          onClick={handleSideView}
          title="Low Profile View (Inspect Elevation Peaks)"
        >
          <span>🏔</span> Profile
        </button>
        <button
          type="button"
          className={`btn btn-sm ${autoRotate ? 'btn-primary' : 'btn-ghost'} venue-3d-btn`}
          onClick={() => setAutoRotate(r => !r)}
          title="Toggle Slow Orbital Rotation"
        >
          <span>🔄</span> {autoRotate ? 'Rotating' : 'Orbit'}
        </button>
        <div className="venue-3d-scale-group">
          <span className="scale-label">Elevation:</span>
          {[
            { label: '1x', val: 1.0 },
            { label: '1.5x', val: 1.5 },
            { label: '2x', val: 2.0 },
          ].map((sc) => (
            <button
              key={sc.label}
              type="button"
              className={`scale-btn ${heightScale === sc.val ? 'scale-btn--active' : ''}`}
              onClick={() => setHeightScale(sc.val)}
            >
              {sc.label}
            </button>
          ))}
        </div>
      </div>

      {/* Camera Guidance Helper in Bottom Left */}
      <div className="venue-3d-hint">
        <span>🖱 Left drag: Rotate · Right drag: Pan · Scroll: Zoom</span>
      </div>
    </div>
  );
}
