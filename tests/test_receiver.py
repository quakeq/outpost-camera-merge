"""Unit tests for packet parsing and receiver resilience."""

import json
import socket
import threading
import time

from outpost.buffers import PoseStore
from outpost.config import CAMERA_IDS, NUM_LANDMARKS
from outpost.receiver import _parse_packet, run_receiver
from tests.helpers import sample_landmarks


def _packet_bytes(camera_id: str = "camera-a", seq: int = 1, t_ms: int = 1000) -> bytes:
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


def test_parse_packet_round_trip():
    data = _packet_bytes("camera-b", seq=42, t_ms=9999)
    frame = _parse_packet(data, "192.168.50.12")
    assert frame.camera_id == "camera-b"
    assert frame.seq == 42
    assert frame.t_capture_ms == 9999
    assert frame.source_ip == "192.168.50.12"
    assert len(frame.landmarks) == NUM_LANDMARKS
    assert frame.landmarks[0].i == 0
    assert frame.receive_ms > 0


def test_parse_packet_malformed_json_raises():
    try:
        _parse_packet(b"not-json", "127.0.0.1")
        assert False, "expected JSONDecodeError"
    except json.JSONDecodeError:
        pass


def test_parse_packet_missing_key_raises():
    data = json.dumps({"camera_id": "camera-a", "seq": 1}).encode("utf-8")
    try:
        _parse_packet(data, "127.0.0.1")
        assert False, "expected KeyError"
    except KeyError:
        pass


def test_receiver_continues_after_bad_packet(monkeypatch, free_udp_port):
    monkeypatch.setenv("OUTPOST_INGEST_PORT", str(free_udp_port))
    # Re-import config bindings used by receiver — patch module attributes directly
    import outpost.config as config
    import outpost.receiver as receiver_mod

    monkeypatch.setattr(config, "INGEST_PORT", free_udp_port)
    monkeypatch.setattr(receiver_mod, "INGEST_PORT", free_udp_port)

    store = PoseStore(CAMERA_IDS, 4)
    stop = threading.Event()
    thread = threading.Thread(target=run_receiver, args=(store, stop), daemon=True)
    thread.start()
    time.sleep(0.05)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(b"{bad", ("127.0.0.1", free_udp_port))
        sock.sendto(_packet_bytes("camera-a", seq=1, t_ms=1000), ("127.0.0.1", free_udp_port))
        # Wait for good packet to land
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if store.nearest_all(1000)["camera-a"] is not None:
                break
            time.sleep(0.02)
        assert store.nearest_all(1000)["camera-a"] is not None
    finally:
        sock.close()
        stop.set()
        thread.join(timeout=2.0)
