"""Compact JSON UDP output for the ESP32."""

from __future__ import annotations

import json
import socket
import time
from typing import Any

from .models import DisplayPacket


class DatagramTooLarge(ValueError):
    """Raised before sending a payload larger than the configured limit."""


def encode_message(message: dict[str, Any], max_bytes: int = 65_507) -> bytes:
    payload = json.dumps(
        message,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=False,
    ).encode("utf-8")
    if len(payload) > max_bytes:
        raise DatagramTooLarge(
            f"encoded datagram is {len(payload)} bytes; limit is {max_bytes}"
        )
    return payload


def encode_display_packet(
    packet: DisplayPacket, max_bytes: int = 65_507
) -> bytes:
    return encode_message(packet.to_wire(), max_bytes=max_bytes)


def encode_heartbeat(
    t_send_ms: int | None = None, max_bytes: int = 65_507
) -> bytes:
    if t_send_ms is None:
        t_send_ms = time.time_ns() // 1_000_000
    return encode_message(
        {"type": "heartbeat", "t_send_ms": t_send_ms},
        max_bytes=max_bytes,
    )


class UdpSender:
    """Send display packets and heartbeats to one ESP32 endpoint."""

    def __init__(
        self,
        host: str,
        port: int,
        *,
        max_datagram_bytes: int = 65_507,
        sock: socket.socket | None = None,
    ) -> None:
        self.destination = (host, port)
        self.max_datagram_bytes = max_datagram_bytes
        self.socket = sock or socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._owns_socket = sock is None

    def send_packet(self, packet: DisplayPacket) -> int:
        return self.socket.sendto(
            encode_display_packet(packet, self.max_datagram_bytes),
            self.destination,
        )

    def send_heartbeat(self, t_send_ms: int | None = None) -> int:
        return self.socket.sendto(
            encode_heartbeat(t_send_ms, self.max_datagram_bytes), self.destination
        )

    def close(self) -> None:
        if self._owns_socket:
            self.socket.close()

    def __enter__(self) -> UdpSender:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
