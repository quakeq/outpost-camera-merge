"""IPs, ports, and timing constants for the fusion node."""

import os

INGEST_HOST = "0.0.0.0"
INGEST_PORT = int(os.environ.get("OUTPOST_INGEST_PORT", "9000"))

DISPLAY_HOST = os.environ.get("OUTPOST_DISPLAY_HOST", "192.168.50.20")
DISPLAY_PORT = int(os.environ.get("OUTPOST_DISPLAY_PORT", "9100"))

CAMERA_IDS = ("phone_a", "phone_b", "phone_c")

FUSION_HZ = 30
SYNC_OFFSET_MS = 30  # target time = now - offset
MAX_POSE_AGE_MS = 100  # mark camera stale beyond this
BUFFER_SIZE = 4  # ~1-2 frames per camera at 30 FPS

NUM_LANDMARKS = 33

CAMERA_A_FOV_DEG = 48
CAMERA_A_POS_MM = [1000,1000,2000, 0, 10, 45] //x,y,z,roll,pitch,yaw #dist in mm, rotation in deg


CAMERA_B_FOV_DEG = 45
