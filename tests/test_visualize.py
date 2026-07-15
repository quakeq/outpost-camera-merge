"""Tests for pose overlay drawing helpers."""

from src.visualize import _image_coords_by_index, draw_pose_overlay_2d
from tests.helpers import sample_landmarks


def test_image_coords_flip_y_axis():
    landmarks = sample_landmarks()
    coords = _image_coords_by_index(landmarks)
    for lm in landmarks:
        x, y = coords[lm.i]
        assert x == lm.x
        assert y == 1.0 - lm.y


def test_draw_pose_overlay_2d_returns_bones():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    try:
        lines = draw_pose_overlay_2d(ax, sample_landmarks())
        assert len(lines) > 0
    finally:
        plt.close(fig)
