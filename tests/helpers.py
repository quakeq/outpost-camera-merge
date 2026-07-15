"""Shared helpers for outpost tests (importable as tests.helpers)."""

from outpost.config import NUM_LANDMARKS
from outpost.models import Landmark, PoseFrame


def sample_landmarks(
    visibility: float = 1.0,
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> list[Landmark]:
    ox, oy, oz = offset
    return [
        Landmark(i=i, x=float(i) + ox, y=float(i) * 0.1 + oy, z=float(i) * 0.01 + oz, v=visibility)
        for i in range(NUM_LANDMARKS)
    ]


def make_pose_frame(
    camera_id: str,
    t_ms: int,
    seq: int,
    *,
    visibility: float = 1.0,
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
    receive_ms: int | None = None,
    source_ip: str = "127.0.0.1",
) -> PoseFrame:
    return PoseFrame(
        camera_id=camera_id,
        seq=seq,
        t_capture_ms=t_ms,
        landmarks=sample_landmarks(visibility=visibility, offset=offset),
        receive_ms=receive_ms if receive_ms is not None else t_ms,
        source_ip=source_ip,
    )
