"""Pose frame and fused pose data models."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class Landmark:
    i: int
    x: float
    y: float
    z: float
    v: float


@dataclass(slots=True)
class PoseFrame:
    camera_id: str
    seq: int
    t_capture_ms: int
    landmarks: list[Landmark]
    receive_ms: int
    source_ip: str


@dataclass(slots=True)
class FusedPose:
    frame_id: int
    t_fused_ms: int
    landmarks: list[Landmark]
    cameras_used: list[str] = field(default_factory=list)
