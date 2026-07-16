"""The 33-point MediaPipe Pose topology used for drawing skeletons."""

from __future__ import annotations

# Bone connections between MediaPipe Pose landmark indices. Matches
# ``mediapipe.solutions.pose.POSE_CONNECTIONS`` so drawn skeletons line up with
# the landmarks produced on the phone.
POSE_CONNECTIONS: tuple[tuple[int, int], ...] = (
    # Face
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 7),
    (0, 4),
    (4, 5),
    (5, 6),
    (6, 8),
    (9, 10),
    # Shoulders
    (11, 12),
    # Left arm and hand
    (11, 13),
    (13, 15),
    (15, 17),
    (15, 19),
    (15, 21),
    (17, 19),
    # Right arm and hand
    (12, 14),
    (14, 16),
    (16, 18),
    (16, 20),
    (16, 22),
    (18, 20),
    # Torso
    (11, 23),
    (12, 24),
    (23, 24),
    # Left leg and foot
    (23, 25),
    (25, 27),
    (27, 29),
    (29, 31),
    (27, 31),
    # Right leg and foot
    (24, 26),
    (26, 28),
    (28, 30),
    (30, 32),
    (28, 32),
)
