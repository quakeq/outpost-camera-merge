"""Unit tests for CameraBuffer and PoseStore."""

from outpost.buffers import CameraBuffer, PoseStore
from tests.helpers import make_pose_frame


def test_push_accepts_increasing_seq():
    buf = CameraBuffer(4)
    assert buf.push(make_pose_frame("phone_a", 1000, 1)) is True
    assert buf.push(make_pose_frame("phone_a", 1033, 2)) is True
    assert buf.latest is not None
    assert buf.latest.seq == 2


def test_push_drops_duplicate_and_out_of_order():
    buf = CameraBuffer(4)
    assert buf.push(make_pose_frame("phone_a", 1000, 5)) is True
    assert buf.push(make_pose_frame("phone_a", 1033, 5)) is False  # duplicate
    assert buf.push(make_pose_frame("phone_a", 1066, 4)) is False  # out-of-order
    assert buf.latest is not None
    assert buf.latest.seq == 5


def test_nearest_picks_closest_timestamp():
    buf = CameraBuffer(4)
    buf.push(make_pose_frame("phone_a", 1000, 1))
    buf.push(make_pose_frame("phone_a", 1100, 2))
    buf.push(make_pose_frame("phone_a", 1200, 3))
    nearest = buf.nearest(1120)
    assert nearest is not None
    assert nearest.t_capture_ms == 1100


def test_nearest_empty_buffer():
    buf = CameraBuffer(4)
    assert buf.nearest(1000) is None
    assert buf.latest is None


def test_pose_store_nearest_all():
    store = PoseStore(("phone_a", "phone_b", "phone_c"), 4)
    store.push(make_pose_frame("phone_a", 1000, 1))
    store.push(make_pose_frame("phone_b", 1010, 1))
    result = store.nearest_all(1005)
    assert result["phone_a"] is not None
    assert result["phone_b"] is not None
    assert result["phone_c"] is None


def test_pose_store_rejects_unknown_camera():
    store = PoseStore(("phone_a", "phone_b", "phone_c"), 4)
    assert store.push(make_pose_frame("phone_z", 1000, 1)) is False
