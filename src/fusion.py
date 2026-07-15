"""Calibrated camera-to-world pose fusion."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from src.config import CAMERA_CONFIG_PATH, MAX_POSE_AGE_MS, NUM_LANDMARKS
from src.models import FusedPose, Landmark, PoseFrame


Matrix3 = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]


@dataclass(frozen=True, slots=True)
class CameraCalibration:
    camera_id: str
    x: float
    y: float
    z: float
    roll: float
    pitch: float
    yaw: float
    fov: float
    rotation: Matrix3


def _matmul(a: Matrix3, b: Matrix3) -> Matrix3:
    return (
        tuple(sum(a[0][k] * b[k][col] for k in range(3)) for col in range(3)),
        tuple(sum(a[1][k] * b[k][col] for k in range(3)) for col in range(3)),
        tuple(sum(a[2][k] * b[k][col] for k in range(3)) for col in range(3)),
    )


def _rotation_matrix(roll_deg: float, pitch_deg: float, yaw_deg: float) -> Matrix3:
    """Return a local camera-space to world-space rotation matrix."""
    roll = math.radians(roll_deg)
    pitch = math.radians(pitch_deg)
    yaw = math.radians(yaw_deg)

    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)

    rx: Matrix3 = ((1.0, 0.0, 0.0), (0.0, cr, -sr), (0.0, sr, cr))
    ry: Matrix3 = ((cp, 0.0, sp), (0.0, 1.0, 0.0), (-sp, 0.0, cp))
    rz: Matrix3 = ((cy, -sy, 0.0), (sy, cy, 0.0), (0.0, 0.0, 1.0))
    return _matmul(_matmul(rz, ry), rx)


def _load_calibrations(path: Path | None = None) -> dict[str, CameraCalibration]:
    calib_path = path or CAMERA_CONFIG_PATH
    with calib_path.open("r", encoding="utf-8") as f:
        raw_cameras = json.load(f)

    calibrations: dict[str, CameraCalibration] = {}
    for raw in raw_cameras:
        camera_id = raw["camera-id"]
        roll = float(raw["roll"])
        pitch = float(raw["pitch"])
        yaw = float(raw["yaw"])
        calibrations[camera_id] = CameraCalibration(
            camera_id=camera_id,
            x=float(raw["x"]),
            y=float(raw["y"]),
            z=float(raw["z"]),
            roll=roll,
            pitch=pitch,
            yaw=yaw,
            fov=float(raw["fov"]),
            rotation=_rotation_matrix(roll, pitch, yaw),
        )
    return calibrations


CAMERA_CALIBRATIONS = _load_calibrations()


def _transform_landmark(lm: Landmark, calibration: CameraCalibration) -> Landmark:
    r = calibration.rotation
    x = calibration.x + r[0][0] * lm.x + r[0][1] * lm.y + r[0][2] * lm.z
    y = calibration.y + r[1][0] * lm.x + r[1][1] * lm.y + r[1][2] * lm.z
    z = calibration.z + r[2][0] * lm.x + r[2][1] * lm.y + r[2][2] * lm.z
    return Landmark(i=lm.i, x=x, y=y, z=z, v=lm.v)


def fuse_poses(
    frames: dict[str, PoseFrame | None],
    target_ms: int,
    frame_id: int,
) -> FusedPose | None:
    """Transform calibrated camera-local landmarks into a shared world pose."""
    active: list[tuple[PoseFrame, CameraCalibration]] = []
    for frame in frames.values():
        if frame is None:
            continue
        if len(frame.landmarks) < NUM_LANDMARKS:
            continue
        calibration = CAMERA_CALIBRATIONS.get(frame.camera_id)
        if calibration is None:
            continue
        if abs(frame.t_capture_ms - target_ms) > MAX_POSE_AGE_MS:
            continue
        active.append((frame, calibration))

    if not active:
        return None

    fused: list[Landmark] = []
    for joint in range(NUM_LANDMARKS):
        world_landmarks = [
            _transform_landmark(frame.landmarks[joint], calibration)
            for frame, calibration in active
        ]
        count = float(len(world_landmarks))
        fused.append(
            Landmark(
                i=joint,
                x=sum(lm.x for lm in world_landmarks) / count,
                y=sum(lm.y for lm in world_landmarks) / count,
                z=sum(lm.z for lm in world_landmarks) / count,
                v=sum(lm.v for lm in world_landmarks) / count,
            )
        )

    return FusedPose(
        frame_id=frame_id,
        t_fused_ms=target_ms,
        landmarks=fused,
        cameras_used=[frame.camera_id for frame, _ in active],
    )
