from __future__ import annotations

import pytest

from outpost.config import Settings, load_settings
from outpost.models import DisplayPacket, DisplayTarget, FilteredFrame, Landmark


def test_settings_reject_invalid_thresholds() -> None:
    with pytest.raises(ValueError, match="min_good_landmarks"):
        Settings(num_landmarks=3, min_good_landmarks=4)
    with pytest.raises(ValueError, match="x_min"):
        Settings(x_min=1.0, x_max=1.0)


def test_load_settings_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OUTPOST_INGEST_PORT", "9012")
    monkeypatch.setenv("OUTPOST_MIN_VISIBILITY", "0.75")
    monkeypatch.setenv("OUTPOST_MOTOR_POLL_MS", "15")
    monkeypatch.setenv("OUTPOST_STEPS_PER_REV", "3200")
    settings = load_settings()
    assert settings.ingest_port == 9012
    assert settings.min_visibility == 0.75
    assert settings.motor_poll_ms == 15
    assert settings.steps_per_rev == 3200


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


def test_display_packet_wire_shape() -> None:
    targets = tuple(
        DisplayTarget(part, 0.1, 0.2, -0.3)
        for part in (
            "head",
            "left_hand",
            "right_hand",
            "left_foot",
            "right_foot",
        )
    )
    packet = DisplayPacket(
        frame_id=7,
        t_capture_ms=123,
        angle=12.5,
        targets=targets,
    )
    assert packet.to_wire() == {
        "frame_id": 7,
        "t_capture_ms": 123,
        "angle": 12.5,
        "targets": [
            {"part": part, "x": 0.1, "y": 0.2, "z": -0.3}
            for part in (
                "head",
                "left_hand",
                "right_hand",
                "left_foot",
                "right_foot",
            )
        ],
    }
