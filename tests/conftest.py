"""Shared fixtures for outpost tests."""

import socket

import pytest

from tests.helpers import make_pose_frame, sample_landmarks

__all__ = ["make_pose_frame", "sample_landmarks", "free_udp_port"]


@pytest.fixture
def free_udp_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port
