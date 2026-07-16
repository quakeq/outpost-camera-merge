# Outpost Landmark Forwarder

Low-latency laptop service for:

```text
Phone MediaPipe → UDP :9000 → validate/filter → UDP :9100 → ESP32
```

Each phone frame is handled independently and forwarded immediately. The laptop
does not fuse cameras or invent replacement landmarks. See [PLAN.md](PLAN.md)
for the complete network and hardware design.

## Install and run

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m outpost.main
```

The defaults listen on `0.0.0.0:9000` and send to
`192.168.50.20:9100`. Add `--verbose` for every decision or `--no-forward`
to validate and log without sending.

The phone and laptop clocks must be synchronized closely enough for the
150 ms stale-frame check. On Linux, allow input with
`sudo ufw allow 9000/udp` if a firewall is active.

## Wire protocol

The phone sends one JSON object per UDP datagram:

```json
{
  "seq": 1842,
  "t_capture_ms": 1784185200123,
  "landmarks": [
    {"i": 0, "x": 0.51, "y": 0.22, "z": -0.08, "v": 0.98}
  ]
}
```

`seq` must increase monotonically for the process lifetime. Timestamps are Unix
epoch milliseconds. Landmark indices must be unique; scalar quality is checked
individually so one bad landmark does not necessarily drop the frame.

The ESP32 receives:

```json
{
  "frame_id": 1842,
  "t_capture_ms": 1784185200123,
  "accepted": [
    {"i": 0, "x": 0.51, "y": 0.22, "z": -0.08, "v": 0.98}
  ],
  "rejected": [1, 2]
}
```

Accepted and rejected indices are sorted. Missing expected landmarks are
rejected explicitly; coordinates are never replaced with zeroes. When no frame
is forwarded for 500 ms, the laptop sends:

```json
{"type":"heartbeat","t_send_ms":1784185200623}
```

## Filtering

A whole frame is discarded for malformed JSON/structure, duplicate indices,
non-increasing sequence, stale/future timestamp, impossible count, or fewer than
the configured minimum number of good landmarks.

Individual landmarks are rejected for unknown index, non-numeric or non-finite
values, visibility below threshold, coordinates outside safety bounds, or a
3D jump from the last successfully forwarded position. A dropped frame never
updates motion history. Rejection counts and forwarding rates are logged
periodically.

Default bounds are intentionally permissive for normalized MediaPipe output:
`x,y = -1.0..2.0` and `z = -4.0..4.0`. Tune them from captured data.

## Configuration

| Environment variable | Default |
|---|---:|
| `OUTPOST_INGEST_HOST` | `0.0.0.0` |
| `OUTPOST_INGEST_PORT` | `9000` |
| `OUTPOST_ESP32_HOST` | `192.168.50.20` |
| `OUTPOST_ESP32_PORT` | `9100` |
| `OUTPOST_NUM_LANDMARKS` | `33` |
| `OUTPOST_MIN_VISIBILITY` | `0.40` |
| `OUTPOST_MAX_FRAME_AGE_MS` | `150` |
| `OUTPOST_MAX_FUTURE_SKEW_MS` | `1000` |
| `OUTPOST_MAX_JUMP_PER_FRAME` | `0.50` |
| `OUTPOST_MIN_GOOD_LANDMARKS` | `4` |
| `OUTPOST_PRIORITY_LANDMARKS` | `13,14,15,16,17,18,19,20,21,22` |
| `OUTPOST_PRIORITY_MIN_VISIBILITY` | `0.05` |
| `OUTPOST_PRIORITY_MAX_JUMP_PER_FRAME` | `1.50` |
| `OUTPOST_X_MIN`, `OUTPOST_X_MAX` | `-1.0`, `2.0` |
| `OUTPOST_Y_MIN`, `OUTPOST_Y_MAX` | `-1.0`, `2.0` |
| `OUTPOST_Z_MIN`, `OUTPOST_Z_MAX` | `-4.0`, `4.0` |
| `OUTPOST_HEARTBEAT_INTERVAL_MS` | `500` |
| `OUTPOST_STATS_INTERVAL_S` | `10` |
| `OUTPOST_MAX_DATAGRAM_BYTES` | `65507` |

All settings are validated at startup.

## Local smoke test

Run these commands in three terminals:

```bash
python tools/mock_display.py
```

```bash
OUTPOST_ESP32_HOST=127.0.0.1 python -m outpost.main --verbose
```

```bash
python tools/mock_phones.py
```

`tools/ingest_monitor.py` inspects phone traffic without filtering.
`tools/phone_sender.py` runs MediaPipe against a webcam, URL, or video after
`pip install -e ".[phone]"`.

## Visualizing the input and output pose

After `pip install -e ".[viz]"`, add `--visualize` to open a live window while
the forwarder runs:

```bash
python -m outpost.main --visualize
```

The left panel draws every landmark the phone sent, with accepted joints in
green and filtered joints in red. The right panel draws only the accepted
landmarks that make up the outgoing frame. Combine with `--no-forward` to
inspect filtering without sending anything to an ESP32.

## Tests

```bash
pytest -v
```

ESP32 firmware, Wi-Fi AP provisioning, and the future compact binary protocol
with CRC are intentionally outside this Python implementation.
