from __future__ import annotations

import pytest

from outpost.models import FilteredFrame, Landmark, RawLandmark
from outpost.skeleton import POSE_CONNECTIONS
from outpost.visualize import (
    PosePoint,
    drawable_bones,
    input_points,
    output_points,
)

from .helpers import frame


def test_pose_connections_reference_valid_landmarks() -> None:
    indices = {i for pair in POSE_CONNECTIONS for i in pair}
    assert indices <= set(range(33))
    assert len(set(POSE_CONNECTIONS)) == len(POSE_CONNECTIONS)


def test_input_points_flag_accepted_and_drop_non_numeric() -> None:
    landmarks = (
        RawLandmark(0, 0.5, 0.5, 0.0, 0.9),
        RawLandmark(1, 0.6, 0.4, 0.0, 0.2),
        RawLandmark(2, "nan-ish", 0.4, 0.0, 0.9),
        RawLandmark(3, float("inf"), 0.4, 0.0, 0.9),
    )
    points = input_points(frame(landmarks=landmarks), accepted_indices={0})

    assert [p.i for p in points] == [0, 1]
    assert {p.i: p.accepted for p in points} == {0: True, 1: False}


def test_output_points_are_all_accepted() -> None:
    output = FilteredFrame(
        frame_id=7,
        t_capture_ms=0,
        accepted=(Landmark(0, 0.5, 0.5, 0.0, 0.9), Landmark(5, 0.6, 0.4, 0.1, 0.8)),
        rejected=(1, 2),
    )
    points = output_points(output)

    assert all(isinstance(p, PosePoint) and p.accepted for p in points)
    assert [p.i for p in points] == [0, 5]


def test_drawable_bones_require_both_endpoints() -> None:
    assert (11, 12) in drawable_bones({11, 12, 13})
    assert (11, 13) in drawable_bones({11, 12, 13})
    assert (13, 15) not in drawable_bones({11, 12, 13})


def test_visualizer_renders_headless() -> None:
    pytest.importorskip("matplotlib")
    from outpost.visualize import PosePairVisualizer

    output = FilteredFrame(
        frame_id=1,
        t_capture_ms=0,
        accepted=(Landmark(11, 0.4, 0.5, 0.0, 0.9), Landmark(12, 0.6, 0.5, 0.0, 0.9)),
        rejected=(0, 1),
    )
    visualizer = PosePairVisualizer(interactive=False)
    try:
        assert visualizer.update(frame(), output) is True
        assert visualizer.update(frame(seq=2), None, dropped_reason="stale") is True
    finally:
        visualizer.close()
