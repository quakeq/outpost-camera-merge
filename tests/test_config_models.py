from __future__ import annotations

import pytest

from outpost.config import Settings, load_settings
from outpost.models import FilteredFrame, Landmark


def test_settings_reject_invalid_thresholds() -> None:
    with pytest.raises(ValueError, match="min_good_landmarks"):
        Settings(num_landmarks=3, min_good_landmarks=4)
    with pytest.raises(ValueError, match="x_min"):
        Settings(x_min=1.0, x_max=1.0)


def test_load_settings_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OUTPOST_INGEST_PORT", "9012")
    monkeypatch.setenv("OUTPOST_MIN_VISIBILITY", "0.75")
    settings = load_settings()
    assert settings.ingest_port == 9012
    assert settings.min_visibility == 0.75


def test_load_settings_reports_bad_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPOST_INGEST_PORT", "nope")
    with pytest.raises(ValueError, match="OUTPOST_INGEST_PORT"):
        load_settings()


def test_filtered_frame_wire_shape() -> None:
    frame = FilteredFrame(
        frame_id=7,
        t_capture_ms=123,
        accepted=(Landmark(1, 0.1, 0.2, -0.3, 0.9),),
        rejected=(0, 2),
    )
    assert frame.to_wire() == {
        "frame_id": 7,
        "t_capture_ms": 123,
        "accepted": [{"i": 1, "x": 0.1, "y": 0.2, "z": -0.3, "v": 0.9}],
        "rejected": [0, 2],
    }
