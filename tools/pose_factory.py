"""Generate fake MediaPipe-style pose packets for testing."""

from __future__ import annotations

import json

NUM_LANDMARKS = 33


def make_landmarks(
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
    visibility: float = 1.0,
) -> list[dict]:
    ox, oy, oz = offset
    return [
        {
            "i": i,
            "x": float(i) * 0.01 + ox,
            "y": float(i) * 0.02 + oy,
            "z": float(i) * 0.005 + oz,
            "v": visibility,
        }
        for i in range(NUM_LANDMARKS)
    ]


def make_packet(
    camera_id: str,
    seq: int,
    t_capture_ms: int,
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
    visibility: float = 1.0,
) -> bytes:
    payload = {
        "camera_id": camera_id,
        "seq": seq,
        "t_capture_ms": t_capture_ms,
        "landmarks": make_landmarks(offset=offset, visibility=visibility),
    }
    return json.dumps(payload).encode("utf-8")
