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
                accepted = message.get("accepted")
                rejected = message.get("rejected")
                if not isinstance(accepted, list) or not isinstance(rejected, list):
                    print(f"{source[0]} malformed landmark lists")
                    continue
                last_frame_id = frame_id
                print(
                    f"{source[0]} frame={frame_id} accepted={len(accepted)} "
                    f"rejected={len(rejected)} bytes={len(data)}"
                )
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
