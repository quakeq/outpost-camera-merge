"""UDP sender for fused poses to the display Pi."""

import json
import socket

from outpost.config import DISPLAY_HOST, DISPLAY_PORT
from outpost.models import FusedPose


def send_fused_pose(sock: socket.socket, pose: FusedPose) -> None:
    payload = {
        "frame_id": pose.frame_id,
        "t_fused_ms": pose.t_fused_ms,
        "cameras_used": pose.cameras_used,
        "landmarks": [
            {"i": lm.i, "x": lm.x, "y": lm.y, "z": lm.z, "v": lm.v}
            for lm in pose.landmarks
        ],
    }
    data = json.dumps(payload).encode("utf-8")
    sock.sendto(data, (DISPLAY_HOST, DISPLAY_PORT))
