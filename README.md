# Outpost Camera Merge

Laptop fusion node for multi-phone MediaPipe pose → synced world skeleton → rotating display Pi.

See [PLAN.md](PLAN.md) for network layout, timing, and architecture.

## Architecture

```
Phone A/B/C  ──UDP :9000──►  Laptop (ingest + fuse @ 30 Hz)  ──UDP :9100──►  Display Pi
```

Phones run MediaPipe; this package only ingests, syncs, and fuses. The fusion stub is a visibility-weighted average (replace with calibrated transforms later).

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

Expect ~30 fused frames/sec on the display mock. Stop one phone sender to see degraded mode (`cameras_used` drops to 2).

## Tests

```bash
pytest -v
```
