"""Side-by-side 2D view of the raw phone pose and the forwarded pose.

The input panel draws every raw landmark the phone sent, coloured by whether
validation accepted it, so filtered joints are obvious. The output panel draws
only the landmarks actually forwarded to the ESP32.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from .models import FilteredFrame, LandmarkFrame
from .skeleton import POSE_CONNECTIONS

ACCEPTED_COLOR = "mediumseagreen"
REJECTED_COLOR = "crimson"
BONE_COLOR = "steelblue"
PANEL_BACKGROUND = "#111111"


@dataclass(frozen=True, slots=True)
class PosePoint:
    """A plottable landmark in normalized MediaPipe image coordinates."""

    i: int
    x: float
    y: float
    accepted: bool


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def input_points(
    frame: LandmarkFrame, accepted_indices: set[int]
) -> list[PosePoint]:
    """Raw landmarks with drawable coordinates, flagged by acceptance."""

    points: list[PosePoint] = []
    for landmark in frame.landmarks:
        x = _finite(landmark.x)
        y = _finite(landmark.y)
        if x is None or y is None:
            continue
        points.append(PosePoint(landmark.i, x, y, landmark.i in accepted_indices))
    return points


def output_points(frame: FilteredFrame) -> list[PosePoint]:
    """Forwarded landmarks, all of which were accepted by definition."""

    return [PosePoint(lm.i, lm.x, lm.y, True) for lm in frame.accepted]


def drawable_bones(indices: set[int]) -> list[tuple[int, int]]:
    """Skeleton connections whose both endpoints are present in ``indices``."""

    return [(i, j) for i, j in POSE_CONNECTIONS if i in indices and j in indices]


class PosePairVisualizer:
    """Two matplotlib panels comparing the input and output poses live."""

    def __init__(self, *, interactive: bool = True) -> None:
        # Imported lazily so the pure helpers above stay usable (and testable)
        # without matplotlib installed.
        import matplotlib

        if not interactive:
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        self._plt = plt
        self._interactive = interactive
        if interactive:
            plt.ion()
        self.fig, (self._input_ax, self._output_ax) = plt.subplots(
            1, 2, figsize=(12, 7)
        )

    def _reset_panel(self, ax: object, title: str) -> None:
        ax.clear()
        ax.set_facecolor(PANEL_BACKGROUND)
        ax.set_xlim(0.0, 1.0)
        ax.set_ylim(0.0, 1.0)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(title)

    def _draw_points(self, ax: object, points: list[PosePoint]) -> None:
        # MediaPipe y grows downward; flip it so poses appear upright.
        coords = {p.i: (p.x, 1.0 - p.y) for p in points}
        for i, j in drawable_bones(set(coords)):
            (x0, y0), (x1, y1) = coords[i], coords[j]
            ax.plot([x0, x1], [y0, y1], color=BONE_COLOR, linewidth=2, zorder=2)

        for accepted, color in ((True, ACCEPTED_COLOR), (False, REJECTED_COLOR)):
            group = [p for p in points if p.accepted is accepted]
            if group:
                ax.scatter(
                    [p.x for p in group],
                    [1.0 - p.y for p in group],
                    c=color,
                    s=28,
                    zorder=3,
                )

    def update(
        self,
        frame: LandmarkFrame,
        output: FilteredFrame | None,
        *,
        dropped_reason: str | None = None,
    ) -> bool:
        """Redraw both panels. Returns ``False`` once the window is closed."""

        if not self._plt.fignum_exists(self.fig.number):
            return False

        accepted_indices = (
            {lm.i for lm in output.accepted} if output is not None else set()
        )
        self._reset_panel(self._input_ax, f"Input (phone) - seq {frame.seq}")
        self._draw_points(self._input_ax, input_points(frame, accepted_indices))

        if output is not None:
            self._reset_panel(
                self._output_ax,
                f"Output (forwarded) - frame {output.frame_id}, "
                f"rejected {len(output.rejected)}",
            )
            self._draw_points(self._output_ax, output_points(output))
        else:
            self._reset_panel(
                self._output_ax, f"Output - frame dropped ({dropped_reason})"
            )
            self._output_ax.text(
                0.5,
                0.5,
                "frame dropped",
                color="#888888",
                ha="center",
                va="center",
                fontsize=14,
            )

        return self._flush()

    def pump(self) -> bool:
        """Service GUI events without redrawing; ``False`` if window closed."""

        if not self._plt.fignum_exists(self.fig.number):
            return False
        return self._flush()

    def _flush(self) -> bool:
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()
        if self._interactive:
            self._plt.pause(0.001)
        return True

    def close(self) -> None:
        if self._plt.fignum_exists(self.fig.number):
            self._plt.close(self.fig)
