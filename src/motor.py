"""Raspberry Pico USB stepper polling and step→degree conversion.

Assumes a 200 full-step/rev motor at 1/16 microstepping (3200 microsteps/rev).
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import threading
import time
from typing import Protocol


_POS_TARGET_RE = re.compile(
    r"pos\s*=\s*(-?\d+)\s+target\s*=\s*(-?\d+)\s*",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class MotorState:
    """Latest polled stepper position and commanded target, in microsteps."""

    position_steps: int
    target_steps: int
    t_poll_ms: int


class MotorClient(Protocol):
    def poll(self) -> MotorState: ...

    def close(self) -> None: ...


def steps_to_degrees(steps: int, steps_per_rev: int) -> float:
    """Map microsteps to shaft angle in ``[0, 360)`` degrees."""

    if steps_per_rev <= 0:
        raise ValueError("steps_per_rev must be positive")
    wrapped = steps % steps_per_rev
    return wrapped * (360.0 / steps_per_rev)


def parse_motor_line(line: str) -> tuple[int, int]:
    """Parse a ``pos=<int> target=<int>`` reply line from the Pico."""

    text = line.strip()
    match = _POS_TARGET_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"unrecognized motor reply: {line!r}")
    return int(match.group(1)), int(match.group(2))


class MockMotorClient:
    """In-process motor that advances position toward a fixed target."""

    def __init__(
        self,
        *,
        position_steps: int = 0,
        target_steps: int = 0,
        step_per_poll: int = 16,
    ) -> None:
        self.position_steps = position_steps
        self.target_steps = target_steps
        self.step_per_poll = step_per_poll

    def poll(self) -> MotorState:
        delta = self.target_steps - self.position_steps
        if delta != 0 and self.step_per_poll > 0:
            step = min(abs(delta), self.step_per_poll)
            self.position_steps += step if delta > 0 else -step
        return MotorState(
            self.position_steps,
            self.target_steps,
            time.time_ns() // 1_000_000,
        )

    def close(self) -> None:
        return None


class UsbSerialMotorClient:
    """Poll a Raspberry Pico stepper controller over USB CDC serial."""

    def __init__(
        self,
        port: str,
        baudrate: int = 115_200,
        *,
        timeout_s: float = 0.05,
        serial_module: object | None = None,
    ) -> None:
        if serial_module is None:
            try:
                import serial as serial_module  # type: ignore[no-redef]
            except ImportError as exc:
                raise ImportError(
                    'install motor deps with: pip install -e ".[motor]"'
                ) from exc
        self._serial = serial_module.Serial(  # type: ignore[attr-defined]
            port=port,
            baudrate=baudrate,
            timeout=timeout_s,
            write_timeout=timeout_s,
        )

    def poll(self) -> MotorState:
        self._serial.reset_input_buffer()
        self._serial.write(b"?\n")
        self._serial.flush()
        raw = self._serial.readline()
        if not raw:
            raise TimeoutError("motor driver did not reply")
        line = raw.decode("utf-8", errors="replace")
        position, target = parse_motor_line(line)
        return MotorState(position, target, time.time_ns() // 1_000_000)

    def close(self) -> None:
        self._serial.close()


class MotorPoller:
    """Background poller that caches the newest successful motor sample."""

    def __init__(
        self,
        client: MotorClient,
        *,
        poll_interval_ms: int,
        stale_ms: int,
    ) -> None:
        if poll_interval_ms <= 0 or stale_ms <= 0:
            raise ValueError("poll and stale intervals must be positive")
        self.client = client
        self.poll_interval_s = poll_interval_ms / 1_000
        self.stale_ms = stale_ms
        self._lock = threading.Lock()
        self._latest: MotorState | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="motor-poller", daemon=True
        )
        self.poll_errors = 0

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)
        self.client.close()

    def latest(self, *, now_ms: int | None = None) -> MotorState | None:
        """Return the cached sample if it is present and not stale."""

        if now_ms is None:
            now_ms = time.time_ns() // 1_000_000
        with self._lock:
            state = self._latest
        if state is None:
            return None
        if now_ms - state.t_poll_ms > self.stale_ms:
            return None
        return state

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                state = self.client.poll()
            except Exception:
                self.poll_errors += 1
            else:
                with self._lock:
                    self._latest = state
            self._stop.wait(self.poll_interval_s)
