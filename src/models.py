"""Wire and validated landmark models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RawLandmark:
    """Structurally complete landmark whose scalar values are not yet trusted."""

    i: int
    x: Any
    y: Any
    z: Any
    v: Any


@dataclass(frozen=True, slots=True)
class Landmark:
    """A validated MediaPipe pose landmark."""

    i: int
    x: float
    y: float
    z: float
    v: float

    def to_wire(self) -> dict[str, int | float]:
        return {"i": self.i, "x": self.x, "y": self.y, "z": self.z, "v": self.v}


@dataclass(frozen=True, slots=True)
class LandmarkFrame:
    """One structurally valid phone datagram."""

    seq: int
    t_capture_ms: int
    landmarks: tuple[RawLandmark, ...]
    receive_ms: int
    source_ip: str


@dataclass(frozen=True, slots=True)
class FilteredFrame:
    """A frame that passed the minimum-good-landmarks threshold."""

    frame_id: int
    t_capture_ms: int
    accepted: tuple[Landmark, ...]
    rejected: tuple[int, ...]

    def to_wire(self) -> dict[str, object]:
        return {
            "frame_id": self.frame_id,
            "t_capture_ms": self.t_capture_ms,
            "accepted": [landmark.to_wire() for landmark in self.accepted],
            "rejected": list(self.rejected),
        }


@dataclass(frozen=True, slots=True)
class DisplayTarget:
    """One validated body endpoint sent to the volumetric display."""

    part: str
    x: float
    y: float
    z: float

    def to_wire(self) -> dict[str, str | float]:
        return {
            "part": self.part,
            "x": self.x,
            "y": self.y,
            "z": self.z,
        }


@dataclass(frozen=True, slots=True)
class DisplayPacket:
    """Current motor angle and five pose targets keyed by pose frame."""

    frame_id: int
    t_capture_ms: int
    angle: float
    targets: tuple[DisplayTarget, ...]

    def to_wire(self) -> dict[str, object]:
        return {
            "frame_id": self.frame_id,
            "t_capture_ms": self.t_capture_ms,
            "angle": self.angle,
            "targets": [target.to_wire() for target in self.targets],
        }
