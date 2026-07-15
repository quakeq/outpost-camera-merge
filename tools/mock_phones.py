#!/usr/bin/env python3
"""Simulate calibrated phones sending UDP pose packets at ~30 Hz."""

from __future__ import annotations

import argparse
import socket
import sys
import time
from pathlib import Path

# Allow running as `python tools/mock_phones.py` without install
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pose_factory import make_packet  # noqa: E402

CAMERA_OFFSETS = {
    "camera-a": (0.0, 0.0, 0.0),
    "camera-b": (0.05, 0.0, 0.0),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Mock calibrated UDP pose senders")
    parser.add_argument("--host", default="127.0.0.1", help="Fusion ingest host")
    parser.add_argument("--port", type=int, default=9000, help="Fusion ingest port")
    parser.add_argument("--hz", type=float, default=30.0, help="Send rate per camera")
    parser.add_argument(
        "--cameras",
        nargs="+",
        default=list(CAMERA_OFFSETS.keys()),
        help="Camera IDs to send (default: all three)",
    )
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    interval = 1.0 / args.hz
    seq = 0

    print(f"Sending {args.cameras} @ {args.hz} Hz → {args.host}:{args.port}")
    try:
        while True:
            t0 = time.perf_counter()
            t_ms = int(time.time() * 1000)
            seq += 1
            for cid in args.cameras:
                offset = CAMERA_OFFSETS.get(cid, (0.0, 0.0, 0.0))
                sock.sendto(make_packet(cid, seq, t_ms, offset=offset), (args.host, args.port))
            elapsed = time.perf_counter() - t0
            time.sleep(max(0.0, interval - elapsed))
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
