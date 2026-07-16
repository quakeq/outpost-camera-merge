"""Strict structural parsing for phone UDP packets."""

from __future__ import annotations

import json
from typing import Any

from .models import LandmarkFrame, RawLandmark


class PacketError(ValueError):
    """A rejected datagram with a stable machine-readable reason."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


def _require_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PacketError("malformed", f"{field} must be an integer")
    if value < 0:
        raise PacketError("malformed", f"{field} cannot be negative")
    return value


def parse_packet(
    data: bytes,
    *,
    receive_ms: int,
    source_ip: str,
    num_landmarks: int = 33,
) -> LandmarkFrame:
    """Decode a datagram and validate frame-level structure.

    Scalar coordinate quality is deliberately left to ``LandmarkValidator`` so
    one bad landmark does not discard an otherwise usable frame.
    """

    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PacketError("invalid_json", "packet is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise PacketError("malformed", "packet root must be an object")

    for field in ("seq", "t_capture_ms", "landmarks"):
        if field not in payload:
            raise PacketError("missing_field", f"packet is missing {field}")

    seq = _require_int(payload["seq"], "seq")
    t_capture_ms = _require_int(payload["t_capture_ms"], "t_capture_ms")
    records = payload["landmarks"]
    if not isinstance(records, list):
        raise PacketError("malformed", "landmarks must be an array")
    if not 1 <= len(records) <= num_landmarks:
        raise PacketError(
            "landmark_count",
            f"landmark count must be between 1 and {num_landmarks}",
        )

    landmarks: list[RawLandmark] = []
    seen: set[int] = set()
    for offset, record in enumerate(records):
        if not isinstance(record, dict):
            raise PacketError("malformed", f"landmark {offset} must be an object")
        for field in ("i", "x", "y", "z", "v"):
            if field not in record:
                raise PacketError(
                    "missing_field", f"landmark {offset} is missing {field}"
                )
        index = _require_int(record["i"], f"landmark {offset} index")
        if index in seen:
            raise PacketError("duplicate_index", f"duplicate landmark index {index}")
        seen.add(index)
        landmarks.append(
            RawLandmark(
                i=index,
                x=record["x"],
                y=record["y"],
                z=record["z"],
                v=record["v"],
            )
        )

    return LandmarkFrame(
        seq=seq,
        t_capture_ms=t_capture_ms,
        landmarks=tuple(landmarks),
        receive_ms=receive_ms,
        source_ip=source_ip,
    )
