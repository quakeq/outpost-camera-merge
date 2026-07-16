from __future__ import annotations

import json

import pytest

from outpost.receiver import PacketError, parse_packet

from .helpers import NOW_MS, packet


def parse(data: bytes):
    return parse_packet(data, receive_ms=NOW_MS, source_ip="127.0.0.1")


def test_parse_valid_packet() -> None:
    frame = parse(packet(seq=9))
    assert frame.seq == 9
    assert frame.t_capture_ms == NOW_MS
    assert len(frame.landmarks) == 33
    assert frame.landmarks[0].i == 0


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (b"{", "invalid_json"),
        (b"[]", "malformed"),
        (b'{"seq":1}', "missing_field"),
        (
            json.dumps(
                {"seq": True, "t_capture_ms": NOW_MS, "landmarks": [{}]}
            ).encode(),
            "malformed",
        ),
        (
            json.dumps(
                {"seq": 1, "t_capture_ms": NOW_MS, "landmarks": []}
            ).encode(),
            "landmark_count",
        ),
    ],
)
def test_parse_rejects_bad_frames(data: bytes, reason: str) -> None:
    with pytest.raises(PacketError) as caught:
        parse(data)
    assert caught.value.reason == reason


def test_parse_rejects_duplicate_indices() -> None:
    landmarks = [
        {"i": 0, "x": 0, "y": 0, "z": 0, "v": 1},
        {"i": 0, "x": 1, "y": 1, "z": 1, "v": 1},
    ]
    with pytest.raises(PacketError) as caught:
        parse(packet(landmarks=landmarks))
    assert caught.value.reason == "duplicate_index"


def test_coordinate_quality_is_deferred_to_validator() -> None:
    landmarks = [{"i": 0, "x": "bad", "y": 0, "z": 0, "v": 1}]
    frame = parse(packet(landmarks=landmarks))
    assert frame.landmarks[0].x == "bad"
