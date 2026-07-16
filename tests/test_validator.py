from __future__ import annotations

from dataclasses import replace
import math

import pytest

from src.config import Settings
from src.models import RawLandmark
from src.validator import LandmarkValidator

from .helpers import NOW_MS, frame, raw_landmarks


def test_accepts_good_frame_and_lists_missing_indices(settings: Settings) -> None:
    validator = LandmarkValidator(settings)
    result = validator.validate(frame(landmarks=raw_landmarks(2)))
    assert result.frame is not None
    assert [item.i for item in result.frame.accepted] == [0, 1]
    assert result.frame.rejected == tuple(range(2, 33))


def test_rejects_stale_future_and_out_of_order_frames(settings: Settings) -> None:
    validator = LandmarkValidator(settings)
    stale = validator.validate(frame(seq=1, capture_ms=NOW_MS - 300))
    assert stale.frame_reason == "stale"

    future = validator.validate(frame(seq=2, capture_ms=NOW_MS + 1_001))
    assert future.frame_reason == "future_timestamp"

    old = validator.validate(frame(seq=2))
    assert old.frame_reason == "out_of_order"


@pytest.mark.parametrize(
    ("candidate", "reason"),
    [
        (RawLandmark(40, 0.5, 0.5, 0.0, 1.0), "unknown_index"),
        (RawLandmark(0, "x", 0.5, 0.0, 1.0), "non_numeric"),
        (RawLandmark(0, math.nan, 0.5, 0.0, 1.0), "non_finite"),
        (RawLandmark(0, 0.5, 0.5, 0.0, 1.1), "invalid_visibility"),
        (RawLandmark(0, 0.5, 0.5, 0.0, 0.1), "low_visibility"),
        (RawLandmark(0, 2.1, 0.5, 0.0, 1.0), "out_of_bounds"),
    ],
)
def test_landmark_rejection_reasons(
    settings: Settings, candidate: RawLandmark, reason: str
) -> None:
    validator = LandmarkValidator(settings)
    other = RawLandmark(1, 0.5, 0.5, 0.0, 1.0)
    result = validator.validate(frame(landmarks=(candidate, other)))
    assert result.frame is None
    assert result.frame_reason == "too_few_good_landmarks"
    assert reason in dict(result.landmark_reasons).values()


def test_partial_filter_forwards_when_minimum_survives(settings: Settings) -> None:
    validator = LandmarkValidator(settings)
    landmarks = (
        RawLandmark(2, 0.5, 0.5, 0.0, 1.0),
        RawLandmark(0, 0.5, 0.5, 0.0, 0.1),
        RawLandmark(1, 0.5, 0.5, 0.0, 1.0),
    )
    result = validator.validate(frame(landmarks=landmarks))
    assert result.frame is not None
    assert [item.i for item in result.frame.accepted] == [1, 2]
    assert 0 in result.frame.rejected


def test_jump_history_is_committed_only_after_forward(settings: Settings) -> None:
    validator = LandmarkValidator(settings)
    first = validator.validate(frame(seq=1, landmarks=raw_landmarks(2)))
    assert first.frame is not None
    validator.commit(first.frame)

    dropped = validator.validate(
        frame(
            seq=2,
            landmarks=(
                RawLandmark(0, 0.7, 0.5, 0.0, 1.0),
                RawLandmark(1, 0.5, 0.5, 0.0, 0.1),
            ),
        )
    )
    assert dropped.frame is None

    next_result = validator.validate(
        frame(
            seq=3,
            landmarks=(
                RawLandmark(0, 1.1, 0.5, 0.0, 1.0),
                RawLandmark(1, 0.5, 0.5, 0.0, 1.0),
            ),
        )
    )
    assert next_result.frame is None
    assert dict(next_result.landmark_reasons)[0] == "implausible_jump"


def test_jump_threshold_is_configurable(settings: Settings) -> None:
    permissive = replace(settings, max_jump_per_frame=1.0)
    validator = LandmarkValidator(permissive)
    first = validator.validate(frame(seq=1, landmarks=raw_landmarks(2)))
    assert first.frame is not None
    validator.commit(first.frame)
    moved = validator.validate(
        frame(seq=2, landmarks=raw_landmarks(2, x=1.0))
    )
    assert moved.frame is not None
