"""30 Hz fusion loop: UDP ingest + fuse + send to display."""

import socket
import threading
import time

from outpost.buffers import PoseStore
from outpost.config import (
    BUFFER_SIZE,
    CAMERA_IDS,
    DISPLAY_HOST,
    DISPLAY_PORT,
    FUSION_HZ,
    SYNC_OFFSET_MS,
)
from outpost.fusion import fuse_poses
from outpost.receiver import run_receiver
from outpost.sender import send_fused_pose


def main() -> None:
    store = PoseStore(CAMERA_IDS, BUFFER_SIZE)
    stop = threading.Event()

    rx = threading.Thread(target=run_receiver, args=(store, stop), daemon=True)
    rx.start()

    display_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    interval = 1.0 / FUSION_HZ
    frame_id = 0

    print(f"Fusion loop at {FUSION_HZ} Hz → {DISPLAY_HOST}:{DISPLAY_PORT}")

    try:
        while True:
            t0 = time.perf_counter()
            now_ms = int(time.time() * 1000)
            target_ms = now_ms - SYNC_OFFSET_MS

            frames = store.nearest_all(target_ms)
            fused = fuse_poses(frames, target_ms, frame_id)
            if fused:
                send_fused_pose(display_sock, fused)
                frame_id += 1

            elapsed = time.perf_counter() - t0
            time.sleep(max(0.0, interval - elapsed))
    except KeyboardInterrupt:
        stop.set()
        rx.join(timeout=1.0)
        display_sock.close()


if __name__ == "__main__":
    main()
