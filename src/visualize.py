"""Matplotlib pose visualization: per-camera 2D overlays and fused 3D view."""

from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 - registers 3d projection

from src.models import FusedPose, Landmark, PoseFrame
from src.skeleton import POSE_CONNECTIONS

VISIBILITY_THRESHOLD = 0.5
AXIS_LENGTH = 0.25
WORLD_LIMIT = 1.5
JOINT_COLOR = "coral"
BONE_COLOR = "steelblue"


def _coords_by_index(landmarks: list[Landmark]) -> dict[int, tuple[float, float, float]]:
    return {lm.i: (lm.x, lm.y, lm.z) for lm in landmarks}


def _visibility_by_index(landmarks: list[Landmark]) -> dict[int, float]:
    return {lm.i: lm.v for lm in landmarks}


def _image_coords_by_index(
    landmarks: list[Landmark],
) -> dict[int, tuple[float, float]]:
    """Map MediaPipe normalized image landmarks to matplotlib 2D coords."""
    return {lm.i: (lm.x, 1.0 - lm.y) for lm in landmarks}


def draw_pose_overlay_2d(
    ax: Axes,
    landmarks: list[Landmark],
    *,
    joint_color: str = JOINT_COLOR,
    bone_color: str = BONE_COLOR,
) -> list[Line2D]:
    """Draw a 2D pose skeleton on a camera-style axes. Returns drawn bone lines."""
    coords = _image_coords_by_index(landmarks)
    visibility = _visibility_by_index(landmarks)
    bone_lines: list[Line2D] = []

    xs = [c[0] for c in coords.values()]
    ys = [c[1] for c in coords.values()]
    ax.scatter(xs, ys, c=joint_color, s=28, zorder=3)

    for i, j in POSE_CONNECTIONS:
        if i not in coords or j not in coords:
            continue
        if visibility.get(i, 0.0) < VISIBILITY_THRESHOLD:
            continue
        if visibility.get(j, 0.0) < VISIBILITY_THRESHOLD:
            continue
        x0, y0 = coords[i]
        x1, y1 = coords[j]
        (line,) = ax.plot([x0, x1], [y0, y1], color=bone_color, linewidth=2, zorder=2)
        bone_lines.append(line)

    return bone_lines


class DualCameraPoseVisualizer:
    """Side-by-side 2D camera panels with live pose overlays."""

    def __init__(self, camera_ids: tuple[str, ...]) -> None:
        plt.ion()
        self._camera_ids = camera_ids
        count = max(len(camera_ids), 1)
        self.fig, axes = plt.subplots(1, count, figsize=(6 * count, 7))
        if count == 1:
            axes = [axes]
        self._axes: list[Axes] = list(axes)
        self._bone_lines: dict[str, list[Line2D]] = {cid: [] for cid in camera_ids}
        self._setup_axes()

    def _setup_axes(self) -> None:
        for ax, camera_id in zip(self._axes, self._camera_ids):
            ax.set_facecolor("#111111")
            ax.set_xlim(0.0, 1.0)
            ax.set_ylim(0.0, 1.0)
            ax.set_aspect("equal")
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title(camera_id)

    def _clear_camera(self, camera_id: str) -> None:
        for line in self._bone_lines[camera_id]:
            line.remove()
        self._bone_lines[camera_id].clear()

    def _draw_no_signal(self, ax: Axes, camera_id: str) -> None:
        ax.clear()
        ax.set_facecolor("#111111")
        ax.set_xlim(0.0, 1.0)
        ax.set_ylim(0.0, 1.0)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.text(
            0.5,
            0.5,
            "no signal",
            color="#666666",
            ha="center",
            va="center",
            fontsize=14,
        )
        ax.set_title(camera_id)

    def update(
        self,
        frames: dict[str, PoseFrame | None],
        fused: FusedPose | None = None,
    ) -> bool:
        """Redraw both camera panels. Returns False if the window was closed."""
        if not plt.fignum_exists(self.fig.number):
            return False

        for camera_id, ax in zip(self._camera_ids, self._axes):
            frame = frames.get(camera_id)
            self._clear_camera(camera_id)
            if frame is None or not frame.landmarks:
                self._draw_no_signal(ax, camera_id)
                continue

            ax.clear()
            ax.set_facecolor("#111111")
            ax.set_xlim(0.0, 1.0)
            ax.set_ylim(0.0, 1.0)
            ax.set_aspect("equal")
            ax.set_xticks([])
            ax.set_yticks([])

            title = f"{camera_id} — seq {frame.seq}"
            if fused is not None:
                title = f"{title} | fused frame {fused.frame_id}"
            ax.set_title(title)
            self._bone_lines[camera_id] = draw_pose_overlay_2d(ax, frame.landmarks)

        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()
        plt.pause(0.001)
        return True

    def close(self) -> None:
        if plt.fignum_exists(self.fig.number):
            plt.close(self.fig)


class PoseVisualizer3D:
    """Live 3D skeleton viewer for fused poses."""

    def __init__(self, title: str = "Fused pose") -> None:
        plt.ion()
        self._title = title
        self.fig = plt.figure(figsize=(9, 8))
        self.ax: Axes3D = self.fig.add_subplot(111, projection="3d")
        self._scatter = None
        self._bone_lines: list[Line2D] = []
        self._setup_world_axes()

    def _setup_world_axes(self) -> None:
        ax = self.ax
        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.set_zlabel("Z (m)")
        ax.set_xlim(-WORLD_LIMIT, WORLD_LIMIT)
        ax.set_ylim(-WORLD_LIMIT, WORLD_LIMIT)
        ax.set_zlim(-WORLD_LIMIT, WORLD_LIMIT)
        try:
            ax.set_box_aspect((1, 1, 1))
        except AttributeError:
            pass

        origin = (0.0, 0.0, 0.0)
        for axis, color in (("x", "tab:red"), ("y", "tab:green"), ("z", "tab:blue")):
            end = [0.0, 0.0, 0.0]
            end[{"x": 0, "y": 1, "z": 2}[axis]] = AXIS_LENGTH
            ax.plot(
                [origin[0], end[0]],
                [origin[1], end[1]],
                [origin[2], end[2]],
                color=color,
                linewidth=2.5,
                alpha=0.85,
            )

    def _clear_bones(self) -> None:
        for line in self._bone_lines:
            line.remove()
        self._bone_lines.clear()

    def _autoscale(self, coords: dict[int, tuple[float, float, float]]) -> None:
        xs = [c[0] for c in coords.values()]
        ys = [c[1] for c in coords.values()]
        zs = [c[2] for c in coords.values()]

        pad = 0.2
        xmin, xmax = min(xs) - pad, max(xs) + pad
        ymin, ymax = min(ys) - pad, max(ys) + pad
        zmin, zmax = min(zs) - pad, max(zs) + pad
        center = (
            (xmin + xmax) / 2,
            (ymin + ymax) / 2,
            (zmin + zmax) / 2,
        )
        radius = max(xmax - xmin, ymax - ymin, zmax - zmin) / 2
        radius = max(radius, 0.5)

        self.ax.set_xlim(center[0] - radius, center[0] + radius)
        self.ax.set_ylim(center[1] - radius, center[1] + radius)
        self.ax.set_zlim(center[2] - radius, center[2] + radius)

    def update(self, fused: FusedPose) -> bool:
        """Redraw the skeleton. Returns False if the window was closed."""
        if not plt.fignum_exists(self.fig.number):
            return False

        coords = _coords_by_index(fused.landmarks)
        if not coords:
            return True

        visibility = _visibility_by_index(fused.landmarks)
        xs = [c[0] for c in coords.values()]
        ys = [c[1] for c in coords.values()]
        zs = [c[2] for c in coords.values()]

        self._autoscale(coords)

        if self._scatter is not None:
            self._scatter.remove()
        self._scatter = self.ax.scatter(xs, ys, zs, c="coral", s=45, depthshade=True)
        self._clear_bones()

        for i, j in POSE_CONNECTIONS:
            if i not in coords or j not in coords:
                continue
            if visibility.get(i, 0.0) < VISIBILITY_THRESHOLD:
                continue
            if visibility.get(j, 0.0) < VISIBILITY_THRESHOLD:
                continue
            x0, y0, z0 = coords[i]
            x1, y1, z1 = coords[j]
            (line,) = self.ax.plot(
                [x0, x1],
                [y0, y1],
                [z0, z1],
                color="steelblue",
                linewidth=2,
            )
            self._bone_lines.append(line)

        self.ax.set_title(
            f"{self._title} — frame {fused.frame_id} | cameras={fused.cameras_used}"
        )
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()
        plt.pause(0.001)
        return True

    def close(self) -> None:
        if plt.fignum_exists(self.fig.number):
            plt.close(self.fig)
