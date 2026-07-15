#!/usr/bin/env python3
"""Print raw pose packets as they arrive on the ingest port."""

from __future__ import annotations

import argparse
import json
import os
import socket
import time


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor UDP pose ingest (debug)")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("OUTPOST_INGEST_PORT", "9000")),
    )
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, args.port))
    sock.settimeout(1.0)

    print(f"Listening for pose packets on {args.host}:{args.port}")
    counts: dict[str, int] = {}
    last_seq: dict[str, int] = {}
    window_start = time.perf_counter()
    total = 0

    try:
        while True:
            try:
                data, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            try:
                msg = json.loads(data.decode("utf-8"))
                cid = msg["camera_id"]
                seq = msg["seq"]
                n_lm = len(msg["landmarks"])
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                print(f"bad packet from {addr[0]}: {exc}")
                continue

            counts[cid] = counts.get(cid, 0) + 1
            total += 1
            gap = ""
            if cid in last_seq and seq != last_seq[cid] + 1:
                gap = f" gap={seq - last_seq[cid] - 1}"
            last_seq[cid] = seq

            if total == 1 or total % 30 == 0:
                elapsed = time.perf_counter() - window_start
                fps = total / elapsed if elapsed > 0 else 0.0
                per_cam = " ".join(f"{k}={v}" for k, v in sorted(counts.items()))
                print(
                    f"{cid} seq={seq} landmarks={n_lm} from {addr[0]} "
                    f"total_fps≈{fps:.1f} [{per_cam}]{gap}"
                )
                if elapsed >= 2.0:
                    counts.clear()
                    total = 0
                    window_start = time.perf_counter()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
