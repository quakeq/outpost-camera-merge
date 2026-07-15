# Outpost Camera Merge

Laptop fusion node for multi-phone MediaPipe pose → synced world skeleton → rotating display Pi.

See [PLAN.md](PLAN.md) for network layout, timing, and architecture.

## Architecture

```
Camera A/B  ──UDP :9000──►  Laptop (ingest + fuse @ 30 Hz)  ──UDP :9100──►  Display Pi
```

Phones run MediaPipe; this package ingests, syncs, transforms each calibrated camera pose into the shared world frame, and fuses those world-frame landmarks.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Requires Python 3.11+.

## Run fusion node

Production (POSE-LAN defaults to display at `192.168.50.20:9100`):

```bash
python -m outpost.main
```

Local testing against mock display:

```bash
OUTPOST_DISPLAY_HOST=127.0.0.1 python -m outpost.main
```

Environment overrides:

| Variable | Default | Meaning |
|----------|---------|---------|
| `OUTPOST_INGEST_PORT` | `9000` | UDP listen port for phone packets |
| `OUTPOST_DISPLAY_HOST` | `192.168.50.20` | Display Pi host |
| `OUTPOST_DISPLAY_PORT` | `9100` | Display UDP port |

## Local smoke test (3 terminals)

```bash
# Terminal 1 — mock display
python tools/mock_display.py

# Terminal 2 — fusion
OUTPOST_DISPLAY_HOST=127.0.0.1 python -m outpost.main

# Terminal 3 — mock phones
python tools/mock_phones.py
```

Expect ~30 fused frames/sec on the display mock. Stop one phone sender to see degraded mode (`cameras_used` drops to 1).

## Tests

```bash
pytest -v
```

## Single phone (real hardware)

One phone is enough — fusion runs in degraded mode with `cameras_used=['camera-a']`.

### 1. Network

Phone and laptop must be on the **same Wi‑Fi** (POSE-LAN or your home LAN).

On POSE-LAN the laptop AP is **`192.168.50.1`** (see [PLAN.md](PLAN.md)). Phones get addresses like `192.168.50.11`–`192.168.50.13`.

If you are not on POSE-LAN, find the laptop IP:

```bash
ip -4 addr show | grep inet
```

Allow ingest through the firewall if enabled:

```bash
sudo ufw allow 9000/udp
```

### 2. Verify ingest (optional)

On the laptop, confirm packets arrive before starting fusion:

```bash
python tools/ingest_monitor.py
```

### 3. Run fusion on the laptop

Without a display Pi (fuse only, log stats):

```bash
python -m outpost.main --no-display
```

With a local mock display:

```bash
# terminal A
python tools/mock_display.py

# terminal B
OUTPOST_DISPLAY_HOST=127.0.0.1 python -m outpost.main
```

Add `--verbose` to see every ingest and fused frame.

### 4. Send pose from the phone

**Option A — Python on the phone (Termux / Pydroid)**

Copy the repo (or at least `tools/phone_sender.py` + `tools/pose_factory.py`) to the phone, install deps, run:

```bash
pip install mediapipe opencv-python
python tools/phone_sender.py --camera-id camera-a
```

(`--host` defaults to `192.168.50.1`; override if your laptop is not the AP.)
```

**Option B — IP Webcam + laptop runs MediaPipe**

Install [IP Webcam](https://play.google.com/store/apps/details?id=com.pas.webcam) on Android, start the server, then on the laptop:

```bash
pip install -e ".[phone]"
python tools/phone_sender.py --host 127.0.0.1 --camera-id camera-a \
  --source "http://PHONE_IP:8080/video"
```

Use a second terminal for fusion (`python -m outpost.main --no-display`). The sender posts to localhost; fusion listens on `0.0.0.0:9000`.

**Option C — Laptop webcam (sanity check before phone)**

```bash
pip install -e ".[phone]"
python tools/phone_sender.py --host 127.0.0.1 --camera-id camera-a --source 0
```

### Packet requirements

The phone must send JSON UDP to `192.168.50.1:9000` (laptop ingest):

| Field | Value |
|-------|-------|
| `camera_id` | `camera-a` or `camera-b` |
| `seq` | monotonically increasing integer |
| `t_capture_ms` | capture time in ms since epoch |
| `landmarks` | 33 entries: `{i, x, y, z, v}` |

### Troubleshooting

| Symptom | Check |
|---------|-------|
| No packets in ingest monitor | Phone IP, laptop firewall, same subnet, correct `--host` |
| Packets but no fused output | Clock skew — `t_capture_ms` must be within ~100 ms of laptop time |
| `bad packet` logs | JSON format or missing fields |
| Low FPS | Lower `--model-complexity 0` on sender; use 5 GHz Wi‑Fi |
