OUTPOST PLAN — LAPTOP (FUSION + ACCESS POINT)
==============================================
Part of: Multi-phone MediaPipe pose → Laptop fusion → Rotating volumetric display
See also: phones.txt, display.txt


ROLE
----

The laptop is the receiver, coordinator, fusion engine, and Wi‑Fi access point. It:
1. Hosts the POSE-LAN Wi‑Fi network (phones and display Pi join here)
2. Ingests UDP pose packets from 3 phones
3. Syncs and fuses poses into one world-coordinate skeleton
4. Sends compact fused pose data to the rotating display Pi

Do not put MediaPipe on the laptop for capture — phones do inference. Do not run
volumetric rendering on the laptop if the display is timing-critical — keep preview
monitors on a lower-priority path.


ARCHITECTURE POSITION
---------------------

Phone A ──┐
Phone B ──┼── Wi‑Fi AP on laptop ──► Laptop (ingest + fuse) ──► Wi‑Fi ──► Rotating display Pi
Phone C ──┘


LAN SETUP
---------

Use a dedicated local network with no internet dependency.

Primary — Laptop as Wi‑Fi access point (recommended)
  Phone A ──┐
  Phone B ──┼── Wi‑Fi AP on laptop
  Phone C ──┘
  Rotating display Pi ── Wi‑Fi

  Pros: one box for AP + fusion, simple addressing, no extra router, easy to isolate
  Cons: AP mode can be fiddly depending on Wi‑Fi chipset/driver; 5 GHz AP support
        varies by adapter

Option B — Small dedicated router/AP (fallback)
  Phones ──► dedicated 5 GHz router/AP ──► Laptop (Ethernet)

  Pros: very stable Wi‑Fi, better range/performance, easier IP management
  Cons: extra device; laptop no longer hosts the AP

Use Option B only if the laptop's Wi‑Fi adapter cannot do reliable AP mode in 5 GHz.


NETWORK SETTINGS
----------------

| Device              | IP               |
|---------------------|------------------|
| Laptop (AP + fuse)  | 192.168.50.1     |
| Phone A             | 192.168.50.11    |
| Phone B             | 192.168.50.12    |
| Phone C             | 192.168.50.13    |
| Rotating display Pi | 192.168.50.20    |

Subnet: 255.255.255.0
SSID: POSE-LAN
Security: WPA2
Band: 5 GHz (preferred; fall back to 2.4 GHz only if hardware requires it)
Channel: fixed (e.g. 36 or 149 depending on region)


IF MAKING THE LAPTOP THE ACCESS POINT
-------------------------------------

On Linux (NetworkManager, hostapd, or create_ap — pick one path and stick with it):

NetworkManager hotspot (quickest to try):
- Use built-in hotspot feature if your adapter supports AP mode
- SSID: POSE-LAN, WPA2, fixed channel if the UI allows it
- Assign static IP 192.168.50.1/24 on the AP interface

hostapd + dnsmasq (more control):
- hostapd for Wi‑Fi AP
- dnsmasq for DHCP
- static IP on wlan0 (192.168.50.1/24)

hostapd:
  SSID: POSE-LAN
  Password: WPA2
  Channel: fixed, not auto
  hw_mode=a (5 GHz) if supported

dnsmasq DHCP range (optional):
  192.168.50.50 – 192.168.50.100

Before going live:
- Confirm AP mode: `iw list` → look for "AP" in Supported interface modes
- Disable power saving on the Wi‑Fi interface
- Keep the laptop plugged in; AP + fusion is steady load

Keep the LAN isolated — no internet sharing needed unless you want phones to pull
SNTP from the laptop.


RECEIVING POSE PACKETS
----------------------

Listen on UDP port 9000 (one shared port with camera_id in each packet).

Why UDP:
- Lower latency
- No connection stalls
- Easy to drop old frames

Firewall (if enabled):
  sudo ufw allow 9000/udp


MINIMAL RECEIVER (Python)
-------------------------

import socket
import json

HOST = "0.0.0.0"
PORT = 9000

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((HOST, PORT))

print(f"Listening on {HOST}:{PORT}")

while True:
    data, addr = sock.recvfrom(65535)
    msg = json.loads(data.decode("utf-8"))

    camera_id = msg["camera_id"]
    seq = msg["seq"]
    t_capture = msg["t_capture_ms"]
    landmarks = msg["landmarks"]

    print(camera_id, seq, len(landmarks), "from", addr[0])

For production use asyncio or dedicated threads, ring buffers per camera, and
timestamp-based sync.


PYTHON FUSION SKETCH (full module layout)
-----------------------------------------

Suggested layout:

  outpost/
    config.py      # IPs, ports, timing constants
    models.py      # PoseFrame, Landmark, FusedPose
    buffers.py     # per-camera ring buffer + nearest-by-time lookup
    receiver.py    # UDP ingest thread
    fusion.py      # transform + fuse (stub weighted average)
    sender.py      # UDP to display Pi
    main.py        # 30 Hz fusion loop

Stdlib only for the prototype (json + threading). Add numpy/opencv when calibration
and triangulation land.


config.py
---------

INGEST_HOST = "0.0.0.0"
INGEST_PORT = 9000

DISPLAY_HOST = "192.168.50.20"
DISPLAY_PORT = 9100

CAMERA_IDS = ("phone_a", "phone_b", "phone_c")

FUSION_HZ = 30
SYNC_OFFSET_MS = 30          # target time = now - offset
MAX_POSE_AGE_MS = 100        # mark camera stale beyond this
BUFFER_SIZE = 4              # ~1-2 frames per camera at 30 FPS

NUM_LANDMARKS = 33


models.py
---------

from dataclasses import dataclass, field

@dataclass(slots=True)
class Landmark:
    i: int
    x: float
    y: float
    z: float
    v: float

@dataclass(slots=True)
class PoseFrame:
    camera_id: str
    seq: int
    t_capture_ms: int
    landmarks: list[Landmark]
    receive_ms: int
    source_ip: str

@dataclass(slots=True)
class FusedPose:
    frame_id: int
    t_fused_ms: int
    landmarks: list[Landmark]
    cameras_used: list[str] = field(default_factory=list)


buffers.py
----------

import time
from collections import deque

from models import PoseFrame

class CameraBuffer:
    def __init__(self, size: int):
        self._buf: deque[PoseFrame] = deque(maxlen=size)
        self._last_seq: int | None = None

    def push(self, frame: PoseFrame) -> bool:
        if self._last_seq is not None and frame.seq <= self._last_seq:
            return False  # duplicate or out-of-order; drop
        self._last_seq = frame.seq
        self._buf.append(frame)
        return True

    def nearest(self, target_ms: int) -> PoseFrame | None:
        if not self._buf:
            return None
        return min(self._buf, key=lambda f: abs(f.t_capture_ms - target_ms))

    @property
    def latest(self) -> PoseFrame | None:
        return self._buf[-1] if self._buf else None


class PoseStore:
    def __init__(self, camera_ids: tuple[str, ...], size: int):
        self._cameras = {cid: CameraBuffer(size) for cid in camera_ids}

    def push(self, frame: PoseFrame) -> bool:
        buf = self._cameras.get(frame.camera_id)
        return buf.push(frame) if buf else False

    def nearest_all(self, target_ms: int) -> dict[str, PoseFrame | None]:
        return {cid: buf.nearest(target_ms) for cid, buf in self._cameras.items()}


receiver.py
-----------

import json
import socket
import threading
import time

from config import INGEST_HOST, INGEST_PORT
from models import Landmark, PoseFrame
from buffers import PoseStore

def _parse_packet(data: bytes, source_ip: str) -> PoseFrame:
    msg = json.loads(data.decode("utf-8"))
    landmarks = [
        Landmark(i=lm["i"], x=lm["x"], y=lm["y"], z=lm["z"], v=lm["v"])
        for lm in msg["landmarks"]
    ]
    return PoseFrame(
        camera_id=msg["camera_id"],
        seq=msg["seq"],
        t_capture_ms=msg["t_capture_ms"],
        landmarks=landmarks,
        receive_ms=int(time.time() * 1000),
        source_ip=source_ip,
    )

def run_receiver(store: PoseStore, stop: threading.Event) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((INGEST_HOST, INGEST_PORT))
    sock.settimeout(0.5)

    while not stop.is_set():
        try:
            data, addr = sock.recvfrom(65535)
            frame = _parse_packet(data, addr[0])
            store.push(frame)
        except socket.timeout:
            continue
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            print("bad packet:", exc)

    sock.close()


fusion.py
---------

from config import MAX_POSE_AGE_MS, NUM_LANDMARKS
from models import FusedPose, Landmark, PoseFrame

def fuse_poses(
    frames: dict[str, PoseFrame | None],
    target_ms: int,
    frame_id: int,
) -> FusedPose | None:
    """Stub fusion: visibility-weighted average per joint.

    Replace with calibrated transforms / triangulation once extrinsics exist.
    """
    active: list[PoseFrame] = []
    for frame in frames.values():
        if frame is None:
            continue
        if abs(frame.t_capture_ms - target_ms) > MAX_POSE_AGE_MS:
            continue
        active.append(frame)

    if not active:
        return None

    fused: list[Landmark] = []
    for joint in range(NUM_LANDMARKS):
        wx = wy = wz = wv = 0.0
        wsum = 0.0
        for frame in active:
            lm = frame.landmarks[joint]
            w = max(lm.v, 0.01)
            wx += lm.x * w
            wy += lm.y * w
            wz += lm.z * w
            wv += lm.v
            wsum += w
        fused.append(Landmark(i=joint, x=wx / wsum, y=wy / wsum, z=wz / wsum, v=wv / len(active)))

    return FusedPose(
        frame_id=frame_id,
        t_fused_ms=target_ms,
        landmarks=fused,
        cameras_used=[f.camera_id for f in active],
    )


sender.py
---------

import json
import socket

from config import DISPLAY_HOST, DISPLAY_PORT
from models import FusedPose

def send_fused_pose(sock: socket.socket, pose: FusedPose) -> None:
    payload = {
        "frame_id": pose.frame_id,
        "t_fused_ms": pose.t_fused_ms,
        "cameras_used": pose.cameras_used,
        "landmarks": [
            {"i": lm.i, "x": lm.x, "y": lm.y, "z": lm.z, "v": lm.v}
            for lm in pose.landmarks
        ],
    }
    data = json.dumps(payload).encode("utf-8")
    sock.sendto(data, (DISPLAY_HOST, DISPLAY_PORT))


main.py
-------

import socket
import threading
import time

from config import BUFFER_SIZE, CAMERA_IDS, FUSION_HZ, SYNC_OFFSET_MS
from buffers import PoseStore
from fusion import fuse_poses
from receiver import run_receiver
from sender import send_fused_pose

def main() -> None:
    store = PoseStore(CAMERA_IDS, BUFFER_SIZE)
    stop = threading.Event()

    rx = threading.Thread(target=run_receiver, args=(store, stop), daemon=True)
    rx.start()

    display_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    interval = 1.0 / FUSION_HZ
    frame_id = 0

    print(f"Fusion loop at {FUSION_HZ} Hz → {DISPLAY_HOST}:{DISPLAY_PORT}")

    try:
        while True:
            t0 = time.perf_counter()
            now_ms = int(time.time() * 1000)
            target_ms = now_ms - SYNC_OFFSET_MS

            frames = store.nearest_all(target_ms)
            fused = fuse_poses(frames, target_ms, frame_id)
            if fused:
                send_fused_pose(display_sock, fused)
                frame_id += 1

            elapsed = time.perf_counter() - t0
            time.sleep(max(0.0, interval - elapsed))
    except KeyboardInterrupt:
        stop.set()
        rx.join(timeout=1.0)
        display_sock.close()

if __name__ == "__main__":
    main()


Run (from outpost/ parent dir):
  python -m outpost.main

Next steps after this sketch runs:
- Load per-camera extrinsics from a calib file; transform landmarks before fuse
- Swap JSON for protobuf/FlatBuffers on ingest and display links
- Add a debug WebSocket that mirrors fused pose for a laptop preview window


SYNC AND FUSION
---------------

Multi-phone pose only works if time and geometry are coherent.

Time:
- Laptop runs chrony/NTP as the time master for the LAN
- Match frames by timestamp, not "latest packet" alone
- Buffer ~1–2 frames (small = lower latency; larger = more reliable sync)

Geometry:
- Calibrate once: intrinsics (phone FOV) + extrinsics (camera positions in room)
- Use a known pattern / person standing on marks
- Store a transform per camera into a shared world frame
- Either triangulate 2D landmarks from ≥2 views into 3D, or transform MediaPipe world
  landmarks into the shared frame and fuse (weighted by visibility / reprojection error)

Per-camera state:
  latest_pose[phone_a]
  latest_pose[phone_b]
  latest_pose[phone_c]

Each update stores: landmarks, seq, timestamp, receive_time

Fusion loop at fixed rate (e.g. 30 Hz):
1. Pick target time = now minus small offset (~30 ms)
2. For each camera, choose nearest pose to that time
3. If pose is too old, mark camera stale
4. Fuse available cameras (down-weight low-visibility joints)
5. Send fused result to rotating display Pi on UDP 9100


SENDING TO DISPLAY PI
---------------------

Send compact fused 3D skeleton / point cloud over UDP to 192.168.50.20:9100.

Prefer sending pose state (option 2) over precomputed volumetric slices (option 1) —
far less bandwidth over Wi‑Fi, and the rotating Pi renders locally based on its angle.


RELIABILITY PATTERNS
--------------------

- Sequence numbers; ignore duplicates; don't block on gaps
- Watchdogs: if a phone drops, keep fusing with 1–2 cameras (degraded mode)
- Heartbeats every 200–500 ms; log per-camera FPS and RTT
- Bound buffers: drop oldest under load (live systems must drop, not queue)


SUGGESTED STACK
---------------

| Layer         | Choice                                   |
|---------------|------------------------------------------|
| AP            | hostapd or NetworkManager hotspot        |
| Ingest        | UDP binary on port 9000                  |
| Control       | TCP or SSH/WebSocket for calib + config  |
| Fusion        | Python or C++ (OpenCV / custom)          |
| Display link  | UDP to rotating Pi on port 9100          |
| Time          | chrony as LAN time master                |


PRACTICAL SETUP SEQUENCE
------------------------

Step 1: Bring up laptop AP (POSE-LAN, static 192.168.50.1, fixed channel)
Step 2: Join phones and display Pi to POSE-LAN; assign static IPs
Step 3: Verify connectivity (ping, test UDP packet)
Step 4: Run fusion receiver (log camera_id, seq, FPS, source IP)
Step 5: Add one phone MediaPipe sender — confirm 20–30 FPS
Step 6: Add second and third phones — confirm no packet loss
Step 7: Add sync/fusion — only after all 3 streams are stable
Step 8: Send fused pose to display Pi


TARGET LATENCY
--------------

End-to-end (capture → fused pose → display update): ~50–120 ms on a clean LAN.
Sub-40 ms needs careful native phone apps + tight sync.
