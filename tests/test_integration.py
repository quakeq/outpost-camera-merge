from __future__ import annotations

from dataclasses import replace
import json
import socket

import pytest

from outpost.config import Settings
from outpost.main import Forwarder
from outpost.sender import DatagramTooLarge, UdpSender, encode_message

from .helpers import NOW_MS, packet


def test_valid_frame_is_forwarded_over_udp(settings: Settings) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(1)
        host, port = receiver.getsockname()
        with UdpSender(host, port) as sender:
            forwarder = Forwarder(settings, sender)
            assert forwarder.process_datagram(
                packet(seq=4), ("127.0.0.1", 5000), receive_ms=NOW_MS
            )
            payload, _ = receiver.recvfrom(65_507)

    message = json.loads(payload)
    assert message["frame_id"] == 4
    assert len(message["accepted"]) == 33
    assert message["rejected"] == []
    assert forwarder.metrics.frames_forwarded == 1


def test_partial_rejection_is_encoded(settings: Settings) -> None:
    landmarks = [
        {"i": 0, "x": 0.5, "y": 0.5, "z": 0, "v": 0.1},
        {"i": 1, "x": 0.5, "y": 0.5, "z": 0, "v": 1},
        {"i": 2, "x": 0.5, "y": 0.5, "z": 0, "v": 1},
    ]
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(1)
        with UdpSender(*receiver.getsockname()) as sender:
            forwarder = Forwarder(settings, sender)
            assert forwarder.process_datagram(
                packet(landmarks=landmarks),
                ("127.0.0.1", 5000),
                receive_ms=NOW_MS,
            )
            payload, _ = receiver.recvfrom(65_507)
    message = json.loads(payload)
    assert [item["i"] for item in message["accepted"]] == [1, 2]
    assert 0 in message["rejected"]
    assert forwarder.metrics.landmark_rejections["low_visibility"] == 1


def test_dropped_and_out_of_order_frames_are_not_sent(
    settings: Settings,
) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(0.05)
        with UdpSender(*receiver.getsockname()) as sender:
            forwarder = Forwarder(settings, sender)
            assert not forwarder.process_datagram(
                packet(seq=2, capture_ms=NOW_MS - 151),
                ("127.0.0.1", 5000),
                receive_ms=NOW_MS,
            )
            assert not forwarder.process_datagram(
                packet(seq=2),
                ("127.0.0.1", 5000),
                receive_ms=NOW_MS,
            )
            with pytest.raises(socket.timeout):
                receiver.recvfrom(65_507)
    assert forwarder.metrics.frame_rejections["stale"] == 1
    assert forwarder.metrics.frame_rejections["out_of_order"] == 1


def test_heartbeat_is_sent_as_json(settings: Settings) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(1)
        with UdpSender(*receiver.getsockname()) as sender:
            forwarder = Forwarder(settings, sender)
            assert forwarder.send_heartbeat(NOW_MS)
            payload, _ = receiver.recvfrom(65_507)
    assert json.loads(payload) == {"type": "heartbeat", "t_send_ms": NOW_MS}
    assert forwarder.metrics.heartbeats_sent == 1


def test_oversized_input_is_not_forwarded(settings: Settings) -> None:
    tiny = replace(settings, max_datagram_bytes=20)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        with UdpSender(
            *receiver.getsockname(), max_datagram_bytes=tiny.max_datagram_bytes
        ) as sender:
            forwarder = Forwarder(tiny, sender)
            assert not forwarder.process_datagram(
                packet(), ("127.0.0.1", 5000), receive_ms=NOW_MS
            )
    assert forwarder.metrics.frame_rejections["datagram_too_large"] == 1


def test_observer_receives_frame_and_result(settings: Settings) -> None:
    seen: list[tuple[int, bool]] = []

    def observer(frame, result) -> None:
        seen.append((frame.seq, result.frame is not None))

    forwarder = Forwarder(settings, None, observer=observer)
    assert forwarder.process_datagram(
        packet(seq=4), ("127.0.0.1", 5000), receive_ms=NOW_MS
    )
    assert not forwarder.process_datagram(
        packet(seq=1, capture_ms=NOW_MS - 151),
        ("127.0.0.1", 5000),
        receive_ms=NOW_MS,
    )

    assert seen == [(4, True), (1, False)]


def test_encoder_enforces_limit() -> None:
    with pytest.raises(DatagramTooLarge):
        encode_message({"value": "long"}, max_bytes=5)
