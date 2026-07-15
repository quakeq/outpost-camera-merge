"""Visibility-weighted pose fusion stub."""

from outpost.config import MAX_POSE_AGE_MS, NUM_LANDMARKS
from outpost.models import FusedPose, Landmark, PoseFrame


def fuse_poses(
    frames: dict[str, PoseFrame | None],
    target_ms: int,
    frame_id: int,
) -> FusedPose | None:
    """Stub fusion: visibility-weighted average per joint.

    Replace with calibrated transforms / triangulation once extrinsics exist.
    """
    active: list[PoseFrame] = []
    for frame in frames.values():
        if frame is None:
            continue
        if abs(frame.t_capture_ms - target_ms) > MAX_POSE_AGE_MS:
            continue
        active.append(frame)

    if not active:
        return None

    fused: list[Landmark] = []
    for joint in range(NUM_LANDMARKS):
        wx = wy = wz = wv = 0.0
        wsum = 0.0
        for frame in active:
            lm = frame.landmarks[joint]
            w = max(lm.v, 0.01)
            wx += lm.x * w
            wy += lm.y * w
            wz += lm.z * w
            wv += lm.v
            wsum += w
        fused.append(
            Landmark(i=joint, x=wx / wsum, y=wy / wsum, z=wz / wsum, v=wv / len(active))
        )

    return FusedPose(
        frame_id=frame_id,
        t_fused_ms=target_ms,
        landmarks=fused,
        cameras_used=[f.camera_id for f in active],
    )
