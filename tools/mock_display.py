#!/usr/bin/env python3
"""Listen for fused pose UDP packets (mock rotating display Pi)."""

from __future__ import annotations

import argparse
import json
import os
import socket
import time


def main() -> None:
    parser = argparse.ArgumentParser(description="Mock display UDP listener")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Bind host",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("OUTPOST_DISPLAY_PORT", "9100")),
        help="Bind port",
    )
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, args.port))
    sock.settimeout(1.0)

    print(f"Listening for fused poses on {args.host}:{args.port}")
    count = 0
    window_start = time.perf_counter()
    try:
        while True:
            try:
                data, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            msg = json.loads(data.decode("utf-8"))
            count += 1
            now = time.perf_counter()
            elapsed = now - window_start
            fps = count / elapsed if elapsed > 0 else 0.0
            if count % 30 == 0 or count == 1:
                print(
                    f"frame_id={msg.get('frame_id')} "
                    f"cameras={msg.get('cameras_used')} "
                    f"landmarks={len(msg.get('landmarks', []))} "
                    f"fps≈{fps:.1f} from {addr[0]}"
                )
                if elapsed >= 2.0:
                    count = 0
                    window_start = now
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
