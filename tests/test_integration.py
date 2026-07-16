from __future__ import annotations

from dataclasses import replace
import json
import socket

import pytest

from outpost.config import Settings
from outpost.main import Forwarder
from outpost.models import DisplayPacket, DisplayTarget
from outpost.motor import MockMotorClient, MotorState, parse_motor_line, steps_to_degrees
from outpost.sender import (
    DatagramTooLarge,
    UdpSender,
    encode_display_packet,
    encode_message,
)

from .helpers import NOW_MS, packet


def test_valid_frame_is_forwarded_over_udp(settings: Settings) -> None:
    motor = MockMotorClient(position_steps=800, target_steps=1600, step_per_poll=0)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(1)
        host, port = receiver.getsockname()
        with UdpSender(host, port) as sender:
            forwarder = Forwarder(settings, sender, motor_client=motor)
            assert forwarder.process_datagram(
                packet(seq=4), ("127.0.0.1", 5000), receive_ms=NOW_MS
            )
            payload, _ = receiver.recvfrom(65_507)

    message = json.loads(payload)
    assert message["frame_id"] == 4
    assert "accepted" not in message
    assert "rejected" not in message
    assert message["angle"] == pytest.approx(90.0)
    assert [target["part"] for target in message["targets"]] == [
        "head",
        "left_hand",
        "right_hand",
        "left_foot",
        "right_foot",
    ]
    assert all(target["x"] == pytest.approx(0.5) for target in message["targets"])
    assert forwarder.metrics.frames_forwarded == 1


def test_stale_motor_skips_forward(settings: Settings) -> None:
    class StaleMotor:
        def poll(self) -> MotorState:
            return MotorState(0, 0, NOW_MS - settings.motor_stale_ms - 1)

        def close(self) -> None:
            return None

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(0.05)
        with UdpSender(*receiver.getsockname()) as sender:
            forwarder = Forwarder(settings, sender, motor_client=StaleMotor())
            assert not forwarder.process_datagram(
                packet(seq=4), ("127.0.0.1", 5000), receive_ms=NOW_MS
            )
            with pytest.raises(socket.timeout):
                receiver.recvfrom(65_507)
    assert forwarder.metrics.frame_rejections["motor_stale"] == 1


def test_missing_body_target_skips_forward(settings: Settings) -> None:
    landmarks = [
        {
            "i": index,
            "x": 0.5,
            "y": 0.5,
            "z": 0.0,
            "v": 0.0 if index == 28 else 0.99,
        }
        for index in range(33)
    ]
    forwarder = Forwarder(settings, None)

    assert not forwarder.process_datagram(
        packet(seq=4, landmarks=landmarks),
        ("127.0.0.1", 5000),
        receive_ms=NOW_MS,
    )
    assert forwarder.metrics.frame_rejections["targets_missing"] == 1


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


def test_display_packet_encoding() -> None:
    targets = (
        DisplayTarget("head", 0.5, 0.1, -0.1),
        DisplayTarget("left_hand", 0.2, 0.4, 0.0),
        DisplayTarget("right_hand", 0.8, 0.4, 0.0),
        DisplayTarget("left_foot", 0.4, 0.9, 0.1),
        DisplayTarget("right_foot", 0.6, 0.9, 0.1),
    )
    packet = DisplayPacket(
        frame_id=3,
        t_capture_ms=10,
        angle=45.0,
        targets=targets,
    )
    payload = encode_display_packet(packet)
    assert json.loads(payload) == {
        "frame_id": 3,
        "t_capture_ms": 10,
        "angle": 45.0,
        "targets": [
            target.to_wire()
            for target in targets
        ],
    }


def test_steps_to_degrees_wraps_at_3200() -> None:
    assert steps_to_degrees(0, 3200) == 0.0
    assert steps_to_degrees(1600, 3200) == 180.0
    assert steps_to_degrees(3200, 3200) == 0.0
    assert steps_to_degrees(4000, 3200) == pytest.approx(90.0)


def test_parse_motor_line() -> None:
    assert parse_motor_line("pos=100 target=200") == (100, 200)
    assert parse_motor_line("POS=-10 TARGET=20\n") == (-10, 20)
    with pytest.raises(ValueError):
        parse_motor_line("ok")
