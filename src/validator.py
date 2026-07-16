"""Stateful frame and landmark quality filtering."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from .config import Settings
from .models import FilteredFrame, Landmark, LandmarkFrame, RawLandmark


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """The forwarding decision and detailed rejection information."""

    frame: FilteredFrame | None
    frame_reason: str | None
    landmark_reasons: tuple[tuple[int, str], ...] = ()


class LandmarkValidator:
    """Validate one ordered phone stream and retain accepted motion history."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._last_seq: int | None = None
        self._positions: dict[int, tuple[float, float, float]] = {}

    @property
    def last_seq(self) -> int | None:
        return self._last_seq

    def validate(self, frame: LandmarkFrame) -> ValidationResult:
        if self._last_seq is not None and frame.seq <= self._last_seq:
            return ValidationResult(None, "out_of_order")

        # A structurally valid sequence number is consumed even if frame quality
        # is poor, preventing delayed replays from being reconsidered.
        self._last_seq = frame.seq
        age_ms = frame.receive_ms - frame.t_capture_ms
        if age_ms > self.settings.max_frame_age_ms:
            return ValidationResult(None, "stale")
        if age_ms < -self.settings.max_future_skew_ms:
            return ValidationResult(None, "future_timestamp")

        accepted: list[Landmark] = []
        reasons: dict[int, str] = {
            index: "missing" for index in range(self.settings.num_landmarks)
        }
        unknown_reasons: list[tuple[int, str]] = []

        for candidate in frame.landmarks:
            landmark, reason = self._validate_landmark(candidate)
            if landmark is None:
                if 0 <= candidate.i < self.settings.num_landmarks:
                    reasons[candidate.i] = reason
                else:
                    unknown_reasons.append((candidate.i, reason))
                continue
            accepted.append(landmark)
            reasons.pop(landmark.i, None)

        accepted.sort(key=lambda item: item.i)
        all_reasons = tuple(sorted(reasons.items())) + tuple(sorted(unknown_reasons))
        if len(accepted) < self.settings.min_good_landmarks:
            return ValidationResult(None, "too_few_good_landmarks", all_reasons)

        return ValidationResult(
            FilteredFrame(
                frame_id=frame.seq,
                t_capture_ms=frame.t_capture_ms,
                accepted=tuple(accepted),
                rejected=tuple(sorted(reasons)),
            ),
            None,
            all_reasons,
        )

    def commit(self, frame: FilteredFrame) -> None:
        """Record positions only after the caller successfully forwards a frame."""

        for landmark in frame.accepted:
            self._positions[landmark.i] = (landmark.x, landmark.y, landmark.z)

    def _validate_landmark(
        self, candidate: RawLandmark
    ) -> tuple[Landmark | None, str]:
        if not 0 <= candidate.i < self.settings.num_landmarks:
            return None, "unknown_index"

        values = (candidate.x, candidate.y, candidate.z, candidate.v)
        if any(not _is_number(value) for value in values):
            return None, "non_numeric"
        x, y, z, visibility = (float(value) for value in values)
        if not all(math.isfinite(value) for value in (x, y, z, visibility)):
            return None, "non_finite"
        if not 0.0 <= visibility <= 1.0:
            return None, "invalid_visibility"

        priority = candidate.i in self.settings.priority_landmarks
        min_visibility = (
            self.settings.priority_min_visibility
            if priority
            else self.settings.min_visibility
        )
        if visibility < min_visibility:
            return None, "low_visibility"
        if not (
            self.settings.x_min <= x <= self.settings.x_max
            and self.settings.y_min <= y <= self.settings.y_max
            and self.settings.z_min <= z <= self.settings.z_max
        ):
            return None, "out_of_bounds"

        max_jump = (
            self.settings.priority_max_jump_per_frame
            if priority
            else self.settings.max_jump_per_frame
        )
        previous = self._positions.get(candidate.i)
        if previous is not None:
            distance = math.dist(previous, (x, y, z))
            if distance > max_jump:
                return None, "implausible_jump"

        return Landmark(candidate.i, x, y, z, visibility), ""


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
