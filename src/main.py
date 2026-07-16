"""Event-driven phone-to-ESP32 landmark forwarder."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
import logging
import signal
import socket
import threading
import time
from typing import Callable, Protocol

from .config import Settings, load_settings
from .models import LandmarkFrame
from .receiver import PacketError, parse_packet
from .sender import DatagramTooLarge, UdpSender
from .validator import LandmarkValidator, ValidationResult


LOGGER = logging.getLogger("outpost")

FrameObserver = Callable[[LandmarkFrame, ValidationResult], None]


class FrameSender(Protocol):
    def send_frame(self, frame: object) -> int: ...

    def send_heartbeat(self, t_send_ms: int | None = None) -> int: ...


@dataclass(slots=True)
class Metrics:
    packets_received: int = 0
    frames_forwarded: int = 0
    heartbeats_sent: int = 0
    backlog_dropped: int = 0
    frame_rejections: Counter[str] = field(default_factory=Counter)
    landmark_rejections: Counter[str] = field(default_factory=Counter)

    def summary(self) -> str:
        return (
            f"received={self.packets_received} "
            f"forwarded={self.frames_forwarded} "
            f"heartbeats={self.heartbeats_sent} "
            f"backlog_dropped={self.backlog_dropped} "
            f"frame_rejections={dict(self.frame_rejections)} "
            f"landmark_rejections={dict(self.landmark_rejections)}"
        )


def recv_latest(
    sock: socket.socket, bufsize: int, timeout: float
) -> tuple[bytes, tuple[str, int], int]:
    """Return the newest queued datagram, discarding any older backlog.

    A live pose stream should always act on the freshest frame, so any
    datagrams already waiting in the kernel receive buffer behind the newest
    one are drained and dropped rather than processed oldest-first. The first
    read honors ``timeout``; the drain is non-blocking. ``timeout`` is restored
    before returning.

    Raises ``socket.timeout`` if no datagram arrives within ``timeout``.
    """

    data, source = sock.recvfrom(bufsize)
    dropped = 0
    sock.setblocking(False)
    try:
        while True:
            try:
                data, source = sock.recvfrom(bufsize)
            except (BlockingIOError, socket.timeout):
                break
            dropped += 1
    finally:
        sock.settimeout(timeout)
    return data, source, dropped


class Forwarder:
    """Parse, filter, and immediately send individual datagrams."""

    def __init__(
        self,
        settings: Settings,
        sender: FrameSender | None,
        *,
        validator: LandmarkValidator | None = None,
        observer: FrameObserver | None = None,
    ) -> None:
        self.settings = settings
        self.sender = sender
        self.validator = validator or LandmarkValidator(settings)
        self.observer = observer
        self.metrics = Metrics()

    def process_datagram(
        self,
        data: bytes,
        source: tuple[str, int],
        *,
        receive_ms: int | None = None,
    ) -> bool:
        self.metrics.packets_received += 1
        if receive_ms is None:
            receive_ms = time.time_ns() // 1_000_000
        if len(data) > self.settings.max_datagram_bytes:
            self._reject("datagram_too_large", source, "incoming payload exceeds limit")
            return False

        try:
            frame = parse_packet(
                data,
                receive_ms=receive_ms,
                source_ip=source[0],
                num_landmarks=self.settings.num_landmarks,
            )
        except PacketError as exc:
            self._reject(exc.reason, source, exc.detail)
            return False

        latency_ms = frame.receive_ms - frame.t_capture_ms
        result = self.validator.validate(frame)
        self.metrics.landmark_rejections.update(
            reason for _, reason in result.landmark_reasons
        )
        if self.observer is not None:
            self.observer(frame, result)
        if result.frame is None:
            self._reject(
                result.frame_reason or "invalid",
                source,
                f"frame rejected latency={latency_ms}",
            )
            return False

        try:
            if self.sender is not None:
                self.sender.send_frame(result.frame)
        except (DatagramTooLarge, OSError) as exc:
            self._reject("send_error", source, str(exc))
            return False

        self.validator.commit(result.frame)
        self.metrics.frames_forwarded += 1
        LOGGER.debug(
            "forwarded frame=%d accepted=%d rejected=%d latency=%d source=%s",
            result.frame.frame_id,
            len(result.frame.accepted),
            len(result.frame.rejected),
            latency_ms,
            source[0],
        )
        return True

    def send_heartbeat(self, now_ms: int | None = None) -> bool:
        if self.sender is None:
            return False
        try:
            self.sender.send_heartbeat(now_ms)
        except (DatagramTooLarge, OSError) as exc:
            self.metrics.frame_rejections["heartbeat_send_error"] += 1
            LOGGER.warning("heartbeat send failed: %s", exc)
            return False
        self.metrics.heartbeats_sent += 1
        return True

    def _reject(
        self, reason: str, source: tuple[str, int], detail: str
    ) -> None:
        self.metrics.frame_rejections[reason] += 1
        LOGGER.debug("rejected source=%s reason=%s detail=%s", source[0], reason, detail)


def run(settings: Settings, *, forward: bool = True, visualize: bool = False) -> None:
    stop = threading.Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    sender = (
        UdpSender(
            settings.esp32_host,
            settings.esp32_port,
            max_datagram_bytes=settings.max_datagram_bytes,
        )
        if forward
        else None
    )

    visualizer = None
    observer: FrameObserver | None = None
    if visualize:
        try:
            from .visualize import PosePairVisualizer
        except ImportError as exc:
            raise SystemExit(
                'install visualization deps with: pip install -e ".[viz]"'
            ) from exc
        visualizer = PosePairVisualizer()

        def observer(frame: LandmarkFrame, result: ValidationResult) -> None:
            if not visualizer.update(
                frame, result.frame, dropped_reason=result.frame_reason
            ):
                stop.set()

    forwarder = Forwarder(settings, sender, observer=observer)
    heartbeat_s = settings.heartbeat_interval_ms / 1_000
    last_output = time.monotonic()
    last_stats = last_output

    recv_timeout = min(heartbeat_s, 0.1)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as ingest:
        ingest.bind((settings.ingest_host, settings.ingest_port))
        ingest.settimeout(recv_timeout)
        LOGGER.info(
            "listening on %s:%d; forwarding=%s",
            settings.ingest_host,
            settings.ingest_port,
            (
                f"{settings.esp32_host}:{settings.esp32_port}"
                if forward
                else "disabled"
            ),
        )
        try:
            while not stop.is_set():
                try:
                    data, source, dropped = recv_latest(
                        ingest, settings.max_datagram_bytes + 1, recv_timeout
                    )
                except socket.timeout:
                    data = b""
                    source = ("", 0)
                else:
                    forwarder.metrics.backlog_dropped += dropped
                if data:
                    if forwarder.process_datagram(data, source):
                        last_output = time.monotonic()
                elif visualizer is not None and not visualizer.pump():
                    stop.set()

                now = time.monotonic()
                if forward and now - last_output >= heartbeat_s:
                    if forwarder.send_heartbeat():
                        last_output = now
                if now - last_stats >= settings.stats_interval_s:
                    LOGGER.info(forwarder.metrics.summary())
                    last_stats = now
        finally:
            if sender is not None:
                sender.close()
            if visualizer is not None:
                visualizer.close()
            LOGGER.info("stopped; %s", forwarder.metrics.summary())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-forward",
        action="store_true",
        help="validate and log packets without sending to an ESP32",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="log every forwarding decision"
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="show a live input-vs-output pose view (needs the viz extra)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        settings = load_settings()
        run(settings, forward=not args.no_forward, visualize=args.visualize)
    except ValueError as exc:
        raise SystemExit(f"configuration error: {exc}") from exc


if __name__ == "__main__":
    main()
