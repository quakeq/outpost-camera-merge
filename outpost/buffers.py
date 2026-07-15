"""Per-camera ring buffers and nearest-by-time lookup."""

from collections import deque

from outpost.models import PoseFrame


class CameraBuffer:
    def __init__(self, size: int):
        self._buf: deque[PoseFrame] = deque(maxlen=size)
        self._last_seq: int | None = None

    def push(self, frame: PoseFrame) -> bool:
        if self._last_seq is not None and frame.seq <= self._last_seq:
            return False  # duplicate or out-of-order; drop
        self._last_seq = frame.seq
        self._buf.append(frame)
        return True

    def nearest(self, target_ms: int) -> PoseFrame | None:
        if not self._buf:
            return None
        return min(self._buf, key=lambda f: abs(f.t_capture_ms - target_ms))

    @property
    def latest(self) -> PoseFrame | None:
        return self._buf[-1] if self._buf else None


class PoseStore:
    def __init__(self, camera_ids: tuple[str, ...], size: int):
        self._cameras = {cid: CameraBuffer(size) for cid in camera_ids}

    def push(self, frame: PoseFrame) -> bool:
        buf = self._cameras.get(frame.camera_id)
        return buf.push(frame) if buf else False

    def nearest_all(self, target_ms: int) -> dict[str, PoseFrame | None]:
        return {cid: buf.nearest(target_ms) for cid, buf in self._cameras.items()}

    def latest_all(self) -> dict[str, PoseFrame | None]:
        return {cid: buf.latest for cid, buf in self._cameras.items()}
