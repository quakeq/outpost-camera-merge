"""Unit tests for calibrated camera-to-world fusion."""

from outpost.config import MAX_POSE_AGE_MS, NUM_LANDMARKS
from outpost.fusion import CameraCalibration, _rotation_matrix, fuse_poses
from outpost.models import Landmark, PoseFrame
from tests.helpers import make_pose_frame


def _calibration(
    camera_id: str,
    offset: tuple[float, float, float],
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> CameraCalibration:
    roll, pitch, yaw = rotation
    return CameraCalibration(
        camera_id=camera_id,
        x=offset[0],
        y=offset[1],
        z=offset[2],
        roll=roll,
        pitch=pitch,
        yaw=yaw,
        fov=45.0,
        rotation=_rotation_matrix(roll, pitch, yaw),
    )


def test_fuse_returns_none_when_all_stale():
    target = 10_000
    frames = {
        "camera-a": make_pose_frame("camera-a", target - MAX_POSE_AGE_MS - 1, 1),
        "camera-b": None,
    }
    assert fuse_poses(frames, target, 0) is None


def test_fuse_returns_none_when_all_missing():
    frames = {"camera-a": None, "camera-b": None}
    assert fuse_poses(frames, 1000, 0) is None


def test_single_camera_transforms_to_world(monkeypatch):
    target = 5000
    monkeypatch.setattr(
        "outpost.fusion.CAMERA_CALIBRATIONS",
        {"camera-a": _calibration("camera-a", (10.0, 20.0, 30.0))},
    )

    frame = make_pose_frame("camera-a", target, 1, offset=(1.0, 2.0, 3.0))
    fused = fuse_poses({"camera-a": frame, "camera-b": None}, target, 7)
    assert fused is not None
    assert fused.frame_id == 7
    assert fused.cameras_used == ["camera-a"]
    assert len(fused.landmarks) == NUM_LANDMARKS
    assert fused.landmarks[0].x == 11.0
    assert fused.landmarks[0].y == 22.0
    assert fused.landmarks[0].z == 33.0


def test_two_camera_calibrated_mean_ignores_visibility_weight(monkeypatch):
    target = 5000
    monkeypatch.setattr(
        "outpost.fusion.CAMERA_CALIBRATIONS",
        {
            "camera-a": _calibration("camera-a", (0.0, 0.0, 0.0)),
            "camera-b": _calibration("camera-b", (10.0, 0.0, 0.0)),
        },
    )

    a = PoseFrame(
        camera_id="camera-a",
        seq=1,
        t_capture_ms=target,
        landmarks=[Landmark(i=i, x=0.0, y=0.0, z=0.0, v=1.0) for i in range(NUM_LANDMARKS)],
        receive_ms=target,
        source_ip="127.0.0.1",
    )
    b = PoseFrame(
        camera_id="camera-b",
        seq=1,
        t_capture_ms=target,
        landmarks=[Landmark(i=i, x=0.0, y=0.0, z=0.0, v=99.0) for i in range(NUM_LANDMARKS)],
        receive_ms=target,
        source_ip="127.0.0.1",
    )
    fused = fuse_poses({"camera-a": a, "camera-b": b}, target, 0)
    assert fused is not None
    assert set(fused.cameras_used) == {"camera-a", "camera-b"}
    assert fused.landmarks[0].x == 5.0
    assert fused.landmarks[0].y == 0.0
    assert fused.landmarks[0].z == 0.0
    assert fused.landmarks[0].v == 50.0


def test_rotation_is_applied_before_translation(monkeypatch):
    target = 5000
    monkeypatch.setattr(
        "outpost.fusion.CAMERA_CALIBRATIONS",
        {"camera-a": _calibration("camera-a", (1.0, 2.0, 3.0), rotation=(0.0, 0.0, 90.0))},
    )

    frame = PoseFrame(
        camera_id="camera-a",
        seq=1,
        t_capture_ms=target,
        landmarks=[Landmark(i=i, x=1.0, y=0.0, z=0.0, v=1.0) for i in range(NUM_LANDMARKS)],
        receive_ms=target,
        source_ip="127.0.0.1",
    )
    fused = fuse_poses({"camera-a": frame}, target, 0)
    assert fused is not None
    assert round(fused.landmarks[0].x, 10) == 1.0
    assert round(fused.landmarks[0].y, 10) == 3.0
    assert round(fused.landmarks[0].z, 10) == 3.0


def test_degraded_mode_skips_stale_and_uncalibrated_cameras():
    target = 5000
    frames = {
        "camera-a": make_pose_frame("camera-a", target, 1),
        "camera-b": make_pose_frame("camera-b", target - MAX_POSE_AGE_MS - 50, 1),
        "camera-c": make_pose_frame("camera-c", target, 1),
    }
    fused = fuse_poses(frames, target, 0)
    assert fused is not None
    assert fused.cameras_used == ["camera-a"]


def test_skips_frames_with_incomplete_landmarks(monkeypatch):
    target = 5000
    monkeypatch.setattr(
        "outpost.fusion.CAMERA_CALIBRATIONS",
        {
            "camera-a": _calibration("camera-a", (0.0, 0.0, 0.0)),
            "camera-b": _calibration("camera-b", (10.0, 0.0, 0.0)),
        },
    )

    incomplete = PoseFrame(
        camera_id="camera-a",
        seq=1,
        t_capture_ms=target,
        landmarks=[],
        receive_ms=target,
        source_ip="127.0.0.1",
    )
    complete = make_pose_frame("camera-b", target, 1, offset=(1.0, 0.0, 0.0))
    fused = fuse_poses({"camera-a": incomplete, "camera-b": complete}, target, 0)
    assert fused is not None
    assert fused.cameras_used == ["camera-b"]
    assert len(fused.landmarks) == NUM_LANDMARKS


def test_returns_none_when_only_incomplete_landmarks():
    target = 5000
    empty = PoseFrame(
        camera_id="camera-a",
        seq=1,
        t_capture_ms=target,
        landmarks=[],
        receive_ms=target,
        source_ip="127.0.0.1",
    )
    assert fuse_poses({"camera-a": empty}, target, 0) is None
