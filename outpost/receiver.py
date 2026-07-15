"""UDP pose ingest thread."""

import json
import socket
import threading
import time

from outpost.buffers import PoseStore
from outpost.config import INGEST_HOST, INGEST_PORT
from outpost.models import Landmark, PoseFrame


def _parse_packet(data: bytes, source_ip: str) -> PoseFrame:
    msg = json.loads(data.decode("utf-8"))
    landmarks = [
        Landmark(i=lm["i"], x=lm["x"], y=lm["y"], z=lm["z"], v=lm["v"])
        for lm in msg["landmarks"]
    ]
    return PoseFrame(
        camera_id=msg["camera_id"],
        seq=msg["seq"],
        t_capture_ms=msg["t_capture_ms"],
        landmarks=landmarks,
        receive_ms=int(time.time() * 1000),
        source_ip=source_ip,
    )


def run_receiver(store: PoseStore, stop: threading.Event) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((INGEST_HOST, INGEST_PORT))
    sock.settimeout(0.5)

    while not stop.is_set():
        try:
            data, addr = sock.recvfrom(65535)
            frame = _parse_packet(data, addr[0])
            store.push(frame)
        except socket.timeout:
            continue
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            print("bad packet:", exc)

    sock.close()
