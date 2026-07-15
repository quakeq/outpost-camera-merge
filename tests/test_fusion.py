"""Unit tests for visibility-weighted fusion."""

from outpost.config import MAX_POSE_AGE_MS, NUM_LANDMARKS
from outpost.fusion import fuse_poses
from outpost.models import Landmark, PoseFrame
from tests.helpers import make_pose_frame


def test_fuse_returns_none_when_all_stale():
    target = 10_000
    frames = {
        "phone_a": make_pose_frame("phone_a", target - MAX_POSE_AGE_MS - 1, 1),
        "phone_b": None,
        "phone_c": None,
    }
    assert fuse_poses(frames, target, 0) is None


def test_fuse_returns_none_when_all_missing():
    frames = {"phone_a": None, "phone_b": None, "phone_c": None}
    assert fuse_poses(frames, 1000, 0) is None


def test_single_camera_passthrough():
    target = 5000
    frame = make_pose_frame("phone_a", target, 1, offset=(1.0, 2.0, 3.0))
    fused = fuse_poses({"phone_a": frame, "phone_b": None, "phone_c": None}, target, 7)
    assert fused is not None
    assert fused.frame_id == 7
    assert fused.cameras_used == ["phone_a"]
    assert len(fused.landmarks) == NUM_LANDMARKS
    assert fused.landmarks[0].x == frame.landmarks[0].x
    assert fused.landmarks[0].y == frame.landmarks[0].y
    assert fused.landmarks[0].z == frame.landmarks[0].z


def test_two_camera_weighted_average():
    target = 5000
    # Equal visibility → arithmetic mean of coords
    a = PoseFrame(
        camera_id="phone_a",
        seq=1,
        t_capture_ms=target,
        landmarks=[Landmark(i=i, x=0.0, y=0.0, z=0.0, v=1.0) for i in range(NUM_LANDMARKS)],
        receive_ms=target,
        source_ip="127.0.0.1",
    )
    b = PoseFrame(
        camera_id="phone_b",
        seq=1,
        t_capture_ms=target,
        landmarks=[Landmark(i=i, x=2.0, y=4.0, z=6.0, v=1.0) for i in range(NUM_LANDMARKS)],
        receive_ms=target,
        source_ip="127.0.0.1",
    )
    fused = fuse_poses({"phone_a": a, "phone_b": b, "phone_c": None}, target, 0)
    assert fused is not None
    assert set(fused.cameras_used) == {"phone_a", "phone_b"}
    assert fused.landmarks[0].x == 1.0
    assert fused.landmarks[0].y == 2.0
    assert fused.landmarks[0].z == 3.0


def test_visibility_weighting():
    target = 5000
    # A has v=1, B has v=3 → weighted avg pulls toward B (3/4 weight on B)
    a = PoseFrame(
        camera_id="phone_a",
        seq=1,
        t_capture_ms=target,
        landmarks=[Landmark(i=i, x=0.0, y=0.0, z=0.0, v=1.0) for i in range(NUM_LANDMARKS)],
        receive_ms=target,
        source_ip="127.0.0.1",
    )
    b = PoseFrame(
        camera_id="phone_b",
        seq=1,
        t_capture_ms=target,
        landmarks=[Landmark(i=i, x=4.0, y=4.0, z=4.0, v=3.0) for i in range(NUM_LANDMARKS)],
        receive_ms=target,
        source_ip="127.0.0.1",
    )
    fused = fuse_poses({"phone_a": a, "phone_b": b}, target, 0)
    assert fused is not None
    # (0*1 + 4*3) / (1+3) = 3.0
    assert fused.landmarks[0].x == 3.0


def test_degraded_mode_skips_stale_third_camera():
    target = 5000
    frames = {
        "phone_a": make_pose_frame("phone_a", target, 1),
        "phone_b": make_pose_frame("phone_b", target, 1),
        "phone_c": make_pose_frame("phone_c", target - MAX_POSE_AGE_MS - 50, 1),
    }
    fused = fuse_poses(frames, target, 0)
    assert fused is not None
    assert "phone_c" not in fused.cameras_used
    assert set(fused.cameras_used) == {"phone_a", "phone_b"}
