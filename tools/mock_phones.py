#!/usr/bin/env python3
"""Send a synthetic single-phone landmark stream."""

from __future__ import annotations

import argparse
import math
import socket
import time

from pose_factory import make_landmarks, make_packet


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--hz", type=float, default=30.0)
    parser.add_argument("--frames", type=int, default=0, help="0 sends forever")
    args = parser.parse_args()
    if args.hz <= 0 or args.frames < 0:
        parser.error("--hz must be positive and --frames cannot be negative")

    destination = (args.host, args.port)
    interval = 1.0 / args.hz
    seq = 0
    next_send = time.monotonic()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            while args.frames == 0 or seq < args.frames:
                phase = seq / args.hz
                landmarks = make_landmarks(
                    x=0.5 + 0.08 * math.sin(phase),
                    y=0.5 + 0.05 * math.cos(phase),
                )
                sock.sendto(make_packet(seq, landmarks), destination)
                seq += 1
                next_send += interval
                time.sleep(max(0.0, next_send - time.monotonic()))
        except KeyboardInterrupt:
            pass
    print(f"sent {seq} frames to {args.host}:{args.port}")


if __name__ == "__main__":
    main()
