"""End-to-end UDP pipeline: mock phones → fusion → mock display."""

import json
import socket
import threading
import time

from outpost.buffers import PoseStore
from outpost.config import BUFFER_SIZE, CAMERA_IDS, FUSION_HZ, NUM_LANDMARKS, SYNC_OFFSET_MS
from outpost.fusion import fuse_poses
from outpost.receiver import run_receiver
from outpost.sender import send_fused_pose
from tests.helpers import sample_landmarks


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _phone_packet(camera_id: str, seq: int, t_ms: int) -> bytes:
    landmarks = [
        {"i": lm.i, "x": lm.x, "y": lm.y, "z": lm.z, "v": lm.v}
        for lm in sample_landmarks()
    ]
    return json.dumps(
        {
            "camera_id": camera_id,
            "seq": seq,
            "t_capture_ms": t_ms,
            "landmarks": landmarks,
        }
    ).encode("utf-8")


def test_end_to_end_fusion_pipeline(monkeypatch):
    ingest_port = _free_port()
    display_port = _free_port()

    import outpost.config as config
    import outpost.receiver as receiver_mod
    import outpost.sender as sender_mod

    monkeypatch.setattr(config, "INGEST_PORT", ingest_port)
    monkeypatch.setattr(config, "DISPLAY_HOST", "127.0.0.1")
    monkeypatch.setattr(config, "DISPLAY_PORT", display_port)
    monkeypatch.setattr(receiver_mod, "INGEST_PORT", ingest_port)
    monkeypatch.setattr(sender_mod, "DISPLAY_HOST", "127.0.0.1")
    monkeypatch.setattr(sender_mod, "DISPLAY_PORT", display_port)

    display_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    display_sock.bind(("127.0.0.1", display_port))
    display_sock.settimeout(0.5)

    store = PoseStore(CAMERA_IDS, BUFFER_SIZE)
    stop = threading.Event()
    rx = threading.Thread(target=run_receiver, args=(store, stop), daemon=True)
    rx.start()

    fused_packets: list[dict] = []
    fusion_done = threading.Event()

    def fusion_loop() -> None:
        out_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        interval = 1.0 / FUSION_HZ
        frame_id = 0
        try:
            while not stop.is_set() and not fusion_done.is_set():
                t0 = time.perf_counter()
                now_ms = int(time.time() * 1000)
                target_ms = now_ms - SYNC_OFFSET_MS
                frames = store.nearest_all(target_ms)
                fused = fuse_poses(frames, target_ms, frame_id)
                if fused:
                    send_fused_pose(out_sock, fused)
                    frame_id += 1
                elapsed = time.perf_counter() - t0
                time.sleep(max(0.0, interval - elapsed))
        finally:
            out_sock.close()

    fusion_thread = threading.Thread(target=fusion_loop, daemon=True)
    fusion_thread.start()
    time.sleep(0.05)

    phone_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Send a burst of aligned frames so SYNC_OFFSET_MS still finds them in-window
        for seq in range(1, 6):
            t_ms = int(time.time() * 1000)
            for cid in CAMERA_IDS:
                phone_sock.sendto(_phone_packet(cid, seq, t_ms), ("127.0.0.1", ingest_port))
            time.sleep(0.02)

        deadline = time.time() + 3.0
        while time.time() < deadline and len(fused_packets) < 2:
            try:
                data, _ = display_sock.recvfrom(65535)
                fused_packets.append(json.loads(data.decode("utf-8")))
            except socket.timeout:
                continue
    finally:
        fusion_done.set()
        stop.set()
        phone_sock.close()
        display_sock.close()
        rx.join(timeout=2.0)
        fusion_thread.join(timeout=2.0)

    assert len(fused_packets) >= 1
    first = fused_packets[0]
    assert len(first["landmarks"]) == NUM_LANDMARKS
    assert set(first["cameras_used"]) == set(CAMERA_IDS)

    if len(fused_packets) >= 2:
        assert fused_packets[1]["frame_id"] > fused_packets[0]["frame_id"]
