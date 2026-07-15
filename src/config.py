"""IPs, ports, and timing constants for the fusion node."""

import json
import os
from pathlib import Path


CAMERA_CONFIG_PATH = Path(__file__).with_name("cameras.json")


def _load_camera_ids() -> tuple[str, ...]:
    with CAMERA_CONFIG_PATH.open("r", encoding="utf-8") as f:
        cameras = json.load(f)
    return tuple(camera["camera-id"] for camera in cameras)


INGEST_HOST = "0.0.0.0"
INGEST_PORT = int(os.environ.get("OUTPOST_INGEST_PORT", "9000"))

DISPLAY_HOST = os.environ.get("OUTPOST_DISPLAY_HOST", "192.168.50.20")
DISPLAY_PORT = int(os.environ.get("OUTPOST_DISPLAY_PORT", "9100"))

CAMERA_IDS = _load_camera_ids()

FUSION_HZ = 30
SYNC_OFFSET_MS = 200  # target time = now - offset
MAX_POSE_AGE_MS = 200  # mark camera stale beyond this
BUFFER_SIZE = 4  # ~1-2 frames per camera at 30 FPS

NUM_LANDMARKS = 33