"""Helpers for producing phone-protocol packets in tools and experiments."""

from __future__ import annotations

import json
import time
from typing import Iterable


def make_landmarks(
    *,
    count: int = 33,
    x: float = 0.5,
    y: float = 0.5,
    z: float = 0.0,
    visibility: float = 0.99,
) -> list[dict[str, int | float]]:
    return [
        {"i": index, "x": x, "y": y, "z": z, "v": visibility}
        for index in range(count)
    ]


def make_packet(
    seq: int,
    landmarks: Iterable[dict[str, int | float]],
    *,
    t_capture_ms: int | None = None,
) -> bytes:
    if t_capture_ms is None:
        t_capture_ms = time.time_ns() // 1_000_000
    return json.dumps(
        {
            "seq": seq,
            "t_capture_ms": t_capture_ms,
            "landmarks": list(landmarks),
        },
        separators=(",", ":"),
    ).encode("utf-8")
