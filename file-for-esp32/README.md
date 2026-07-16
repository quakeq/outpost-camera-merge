# ESP32 volumetric display firmware for Outpost

Flash [`outpost_display/outpost_display.ino`](outpost_display/outpost_display.ino)
with the Arduino IDE (ESP32 board package) and the [FastLED](https://github.com/FastLED/FastLED)
library.

## What it does

Joins **POSE-LAN** as `192.168.50.20`, listens for laptop UDP JSON on port
**9100**, and paints a 16×16 WS2812 panel for the current shaft `angle`.

```text
Laptop  ── JSON angle + 5 targets :9100 ──►  ESP32  ──►  WS2812 16×16
Pico USB motor (separate) supplies angle via the laptop forwarder
```

Packet shapes match `outpost.sender`:

```json
{
  "frame_id": 1842,
  "t_capture_ms": 1784185200123,
  "angle": 137.25,
  "targets": [
    {"part": "head", "x": 0.50, "y": 0.20, "z": -0.10},
    {"part": "left_hand", "x": 0.20, "y": 0.40, "z": 0.00},
    {"part": "right_hand", "x": 0.80, "y": 0.40, "z": 0.00},
    {"part": "left_foot", "x": 0.40, "y": 0.90, "z": 0.10},
    {"part": "right_foot", "x": 0.60, "y": 0.90, "z": 0.10}
  ]
}
```

The cylinder body remains static. Only those five points move; the ESP32 does
not animate a skeleton, torso, or motor target.

```json
{"type":"heartbeat","t_send_ms":1784185200623}
```

Duplicate or older `frame_id` values are ignored. After 1 s without a packet
the panel blanks; while waiting for the first frame an idle chase runs.

## Wiring

| ESP32 | Panel        |
|-------|--------------|
| GPIO 2 (default `LED_PIN`) | WS2812 DIN |
| GND   | GND          |

Power the matrix from a stout **5 V** supply (not the ESP32 5 V pin). Common
ground is required. Edit `LED_PIN` / brightness in
[`outpost_display/config.h`](outpost_display/config.h).

## Config to edit before flash

In [`outpost_display/config.h`](outpost_display/config.h):

| Symbol | Default | Notes |
|--------|---------|--------|
| `WIFI_SSID` | `POSE-LAN` | Must match the laptop AP / router |
| `WIFI_PASS` | `outpost123` | Change to your WPA2 passphrase |
| `WIFI_IP` | `192.168.50.20` | Reserved ESP32 address from PLAN.md |
| `UDP_PORT` | `9100` | `OUTPOST_ESP32_PORT` |
| `LED_PIN` | `2` | WS2812 data |

## Bring-up

1. Flash the sketch; open serial at 115200 — expect `IP 192.168.50.20` and
   `outpost_display ready`.
2. On the laptop, run the mock display check against the real board:

```bash
OUTPOST_ESP32_HOST=192.168.50.20 python -m outpost.main --verbose
```

Or send one packet:

```bash
python -c "
import socket, json
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.sendto(json.dumps({
  'frame_id': 1,
  't_capture_ms': 0,
  'angle': 45.0,
  'targets': [
    {'part':'head', 'x':.5, 'y':.2, 'z':-.1},
    {'part':'left_hand', 'x':.2, 'y':.4, 'z':0},
    {'part':'right_hand', 'x':.8, 'y':.4, 'z':0},
    {'part':'left_foot', 'x':.4, 'y':.9, 'z':.1},
    {'part':'right_foot', 'x':.6, 'y':.9, 'z':.1},
  ],
}).encode(), ('192.168.50.20', 9100))
"
```

You should see the dim cyan cylinder body plus the five colored target points
when they intersect the panel's current rotational slice.

## Safety

A spinning LED panel is a mechanical hazard. Start at low RPM, secure wiring
(slip ring or careful cable management), and keep hands clear of the sweep.
