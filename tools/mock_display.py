#!/usr/bin/env python3
"""Receive and inspect the JSON datagrams expected by the ESP32."""

from __future__ import annotations

import argparse
import json
import socket


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9100)
    args = parser.parse_args()

    last_frame_id = -1
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((args.host, args.port))
        print(f"mock ESP32 listening on UDP {args.host}:{args.port}")
        try:
            while True:
                data, source = sock.recvfrom(65_508)
                try:
                    message = json.loads(data)
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    print(f"{source[0]} malformed payload: {exc}")
                    continue
                if message.get("type") == "heartbeat":
                    print(f"{source[0]} heartbeat t_send_ms={message.get('t_send_ms')}")
                    continue
                frame_id = message.get("frame_id")
                if not isinstance(frame_id, int) or frame_id <= last_frame_id:
                    print(f"{source[0]} rejected frame_id={frame_id!r}")
                    continue
                angle = message.get("angle")
                targets = message.get("targets")
                if not isinstance(angle, (int, float)) or not isinstance(
                    targets, list
                ):
                    print(f"{source[0]} malformed angle/targets")
                    continue
                parts = [
                    target.get("part")
                    for target in targets
                    if isinstance(target, dict)
                ]
                if parts != [
                    "head",
                    "left_hand",
                    "right_hand",
                    "left_foot",
                    "right_foot",
                ]:
                    print(f"{source[0]} malformed targets={parts!r}")
                    continue
                last_frame_id = frame_id
                print(
                    f"{source[0]} frame={frame_id} angle={angle} "
                    f"targets={len(targets)} bytes={len(data)}"
                )
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
