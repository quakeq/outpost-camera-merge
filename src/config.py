"""Environment-backed configuration for the laptop forwarder."""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from typing import Callable, TypeVar


T = TypeVar("T")


def _env(name: str, default: T, convert: Callable[[str], T]) -> T:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return convert(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} has invalid value {value!r}") from exc


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings, with conservative MediaPipe normalized-coordinate bounds."""

    ingest_host: str = "0.0.0.0"
    ingest_port: int = 9000
    esp32_host: str = "192.168.50.20"
    esp32_port: int = 9100
    num_landmarks: int = 33
    min_visibility: float = 0.10
    max_frame_age_ms: int = 500
    max_future_skew_ms: int = 1000
    max_jump_per_frame: float = 1
    min_good_landmarks: int = 4
    # Elbows (13, 14) and hands (wrists and fingers, 15-22) drive the interaction
    # gestures we care about, so they are kept unless egregiously bad: their
    # visibility and motion thresholds are relaxed relative to other landmarks.
    priority_landmarks: frozenset[int] = frozenset(range(13, 23))
    priority_min_visibility: float = 0.05
    priority_max_jump_per_frame: float = 1.50
    x_min: float = -1.00
    x_max: float = 2.00
    y_min: float = -1.00
    y_max: float = 2.00
    z_min: float = -4.00
    z_max: float = 4.00
    heartbeat_interval_ms: int = 500
    stats_interval_s: float = 10.0
    max_datagram_bytes: int = 65_507
    # Raspberry Pico USB CDC; empty port uses an in-process mock motor.
    motor_port: str = ""
    motor_baud: int = 115_200
    motor_poll_ms: int = 20
    motor_stale_ms: int = 100
    # 200 full steps/rev × 1/16 microstepping.
    steps_per_rev: int = 3_200

    def __post_init__(self) -> None:
        for name, value in (
            ("ingest_port", self.ingest_port),
            ("esp32_port", self.esp32_port),
        ):
            if not 1 <= value <= 65_535:
                raise ValueError(f"{name} must be between 1 and 65535")
        if self.num_landmarks <= 0:
            raise ValueError("num_landmarks must be positive")
        if not 0.0 <= self.min_visibility <= 1.0:
            raise ValueError("min_visibility must be between 0 and 1")
        if not 0.0 <= self.priority_min_visibility <= 1.0:
            raise ValueError("priority_min_visibility must be between 0 and 1")
        if not 1 <= self.min_good_landmarks <= self.num_landmarks:
            raise ValueError("min_good_landmarks must be within landmark count")
        if any(
            not 0 <= index < self.num_landmarks for index in self.priority_landmarks
        ):
            raise ValueError("priority_landmarks must be valid landmark indices")
        if self.max_frame_age_ms < 0 or self.max_future_skew_ms < 0:
            raise ValueError("frame age limits cannot be negative")
        for name, value in (
            ("max_jump_per_frame", self.max_jump_per_frame),
            ("priority_max_jump_per_frame", self.priority_max_jump_per_frame),
        ):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive")
        if (
            self.heartbeat_interval_ms <= 0
            or not math.isfinite(self.stats_interval_s)
            or self.stats_interval_s <= 0
        ):
            raise ValueError("heartbeat and stats intervals must be positive")
        if self.max_datagram_bytes <= 0 or self.max_datagram_bytes > 65_507:
            raise ValueError("max_datagram_bytes must be within the UDP payload limit")
        if self.motor_baud <= 0:
            raise ValueError("motor_baud must be positive")
        if self.motor_poll_ms <= 0 or self.motor_stale_ms <= 0:
            raise ValueError("motor poll and stale intervals must be positive")
        if self.steps_per_rev <= 0:
            raise ValueError("steps_per_rev must be positive")
        for axis in ("x", "y", "z"):
            lower = getattr(self, f"{axis}_min")
            upper = getattr(self, f"{axis}_max")
            if not math.isfinite(lower) or not math.isfinite(upper) or lower >= upper:
                raise ValueError(f"{axis}_min must be less than {axis}_max")


def _parse_index_set(value: str) -> frozenset[int]:
    return frozenset(int(part) for part in value.split(",") if part.strip())


def load_settings() -> Settings:
    """Load settings from OUTPOST_* environment variables."""

    return Settings(
        ingest_host=os.getenv("OUTPOST_INGEST_HOST", "0.0.0.0"),
        ingest_port=_env("OUTPOST_INGEST_PORT", 9000, int),
        esp32_host=os.getenv("OUTPOST_ESP32_HOST", "192.168.50.20"),
        esp32_port=_env("OUTPOST_ESP32_PORT", 9100, int),
        num_landmarks=_env("OUTPOST_NUM_LANDMARKS", 33, int),
        min_visibility=_env("OUTPOST_MIN_VISIBILITY", 0.40, float),
        max_frame_age_ms=_env("OUTPOST_MAX_FRAME_AGE_MS", 300, int),
        max_future_skew_ms=_env("OUTPOST_MAX_FUTURE_SKEW_MS", 1_000, int),
        max_jump_per_frame=_env("OUTPOST_MAX_JUMP_PER_FRAME", 0.50, float),
        min_good_landmarks=_env("OUTPOST_MIN_GOOD_LANDMARKS", 4, int),
        priority_landmarks=_env(
            "OUTPOST_PRIORITY_LANDMARKS", frozenset(range(13, 23)), _parse_index_set
        ),
        priority_min_visibility=_env("OUTPOST_PRIORITY_MIN_VISIBILITY", 0.05, float),
        priority_max_jump_per_frame=_env(
            "OUTPOST_PRIORITY_MAX_JUMP_PER_FRAME", 1.50, float
        ),
        x_min=_env("OUTPOST_X_MIN", -1.00, float),
        x_max=_env("OUTPOST_X_MAX", 2.00, float),
        y_min=_env("OUTPOST_Y_MIN", -1.00, float),
        y_max=_env("OUTPOST_Y_MAX", 2.00, float),
        z_min=_env("OUTPOST_Z_MIN", -4.00, float),
        z_max=_env("OUTPOST_Z_MAX", 4.00, float),
        heartbeat_interval_ms=_env("OUTPOST_HEARTBEAT_INTERVAL_MS", 500, int),
        stats_interval_s=_env("OUTPOST_STATS_INTERVAL_S", 10.0, float),
        max_datagram_bytes=_env("OUTPOST_MAX_DATAGRAM_BYTES", 65_507, int),
        motor_port=os.getenv("OUTPOST_MOTOR_PORT", ""),
        motor_baud=_env("OUTPOST_MOTOR_BAUD", 115_200, int),
        motor_poll_ms=_env("OUTPOST_MOTOR_POLL_MS", 20, int),
        motor_stale_ms=_env("OUTPOST_MOTOR_STALE_MS", 100, int),
        steps_per_rev=_env("OUTPOST_STEPS_PER_REV", 3_200, int),
    )
