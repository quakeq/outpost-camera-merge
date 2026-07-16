from __future__ import annotations

import json

from outpost.models import LandmarkFrame, RawLandmark


NOW_MS = 1_784_185_200_123


def raw_landmarks(
    count: int = 33,
    *,
    x: object = 0.5,
    y: object = 0.5,
    z: object = 0.0,
    visibility: object = 0.99,
) -> tuple[RawLandmark, ...]:
    return tuple(
        RawLandmark(index, x, y, z, visibility) for index in range(count)
    )


def frame(
    seq: int = 1,
    *,
    landmarks: tuple[RawLandmark, ...] | None = None,
    capture_ms: int = NOW_MS,
    receive_ms: int = NOW_MS,
) -> LandmarkFrame:
    return LandmarkFrame(
        seq=seq,
        t_capture_ms=capture_ms,
        landmarks=landmarks if landmarks is not None else raw_landmarks(),
        receive_ms=receive_ms,
        source_ip="192.168.50.11",
    )


def packet(
    seq: int = 1,
    *,
    landmarks: list[dict[str, object]] | None = None,
    capture_ms: int = NOW_MS,
) -> bytes:
    if landmarks is None:
        landmarks = [
            {"i": index, "x": 0.5, "y": 0.5, "z": 0.0, "v": 0.99}
            for index in range(33)
        ]
    return json.dumps(
        {"seq": seq, "t_capture_ms": capture_ms, "landmarks": landmarks},
        separators=(",", ":"),
    ).encode()
