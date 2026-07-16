#!/usr/bin/env python3
"""Inspect and structurally validate raw phone packets without forwarding."""

from __future__ import annotations

import argparse
from collections import Counter
import socket
import time

from outpost.receiver import PacketError, parse_packet


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args()

    counts: Counter[str] = Counter()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((args.host, args.port))
        print(f"monitoring UDP {args.host}:{args.port}")
        try:
            while True:
                data, source = sock.recvfrom(65_508)
                now_ms = time.time_ns() // 1_000_000
                try:
                    frame = parse_packet(
                        data,
                        receive_ms=now_ms,
                        source_ip=source[0],
                    )
                except PacketError as exc:
                    counts[exc.reason] += 1
                    print(f"{source[0]} rejected={exc.reason}: {exc.detail}")
                    continue
                counts["valid"] += 1
                age_ms = now_ms - frame.t_capture_ms
                print(
                    f"{source[0]} seq={frame.seq} landmarks={len(frame.landmarks)} "
                    f"age_ms={age_ms} counts={dict(counts)}"
                )
        except KeyboardInterrupt:
            pass
    print(dict(counts))


if __name__ == "__main__":
    main()
