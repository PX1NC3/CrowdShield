/**
 * cameraSpatialConfig.js
 * Camera-specific spatial configuration isolated for Part 1 & Part 2.
 * Part 1 uses a normalized coordinate plane.
 * Part 2 will plug in separate homography matrix, physical boundary offsets,
 * camera height/pitch angle, and coordinate transforms here without altering the 3D visualizer.
 */

export const CAMERA_SPATIAL_CONFIGS = {
  cam1: {
    id: 'cam1',
    name: 'Camera 1 — Main Entrance Gate A',
    viewLabel: 'GATE A FOV (NORMALIZED)',
    planeSize: [14, 10],
    planeWidth: 14,
    planeDepth: 10,
    gridDivisions: 10,
    accentColor: '#7c3aed',
    defaultCameraPos: [0, 8.5, 11],
    defaultTarget: [0, 0, 0.5],
    // Part 2 placeholder for calibration matrix / homography
    calibration: {
      isCalibrated: false,
      homographyMatrix: null,
      fieldOfViewDegrees: 78,
      mountingHeightMeters: 4.2,
      tiltDegrees: 28,
    },
  },
  cam2: {
    id: 'cam2',
    name: 'Camera 2 — South Corridor Gate B',
    viewLabel: 'GATE B FOV (NORMALIZED)',
    planeSize: [14, 10],
    planeWidth: 14,
    planeDepth: 10,
    gridDivisions: 10,
    accentColor: '#7c3aed',
    defaultCameraPos: [0, 8.5, 11],
    defaultTarget: [0, 0, 0.5],
    // Part 2 placeholder for calibration matrix / homography
    calibration: {
      isCalibrated: false,
      homographyMatrix: null,
      fieldOfViewDegrees: 84,
      mountingHeightMeters: 3.8,
      tiltDegrees: 32,
    },
  },
};

export function getCameraSpatialConfig(camId) {
  return CAMERA_SPATIAL_CONFIGS[camId] || {
    id: camId,
    name: `Camera ${camId ? camId.toUpperCase() : 'FEED'}`,
    viewLabel: `${camId ? camId.toUpperCase() : 'FEED'} FOV (NORMALIZED)`,
    planeSize: [14, 10],
    planeWidth: 14,
    planeDepth: 10,
    gridDivisions: 10,
    accentColor: '#7c3aed',
    defaultCameraPos: [0, 8.5, 11],
    defaultTarget: [0, 0, 0.5],
    calibration: { isCalibrated: false, homographyMatrix: null },
  };
}
