# ESP32 volumetric display firmware for Outpost

Flash [`outpost_display/outpost_display.ino`](outpost_display/outpost_display.ino)
with the Arduino IDE (ESP32 board package) and the [FastLED](https://github.com/FastLED/FastLED)
library. The sketch is self-contained; there are no additional source tabs.

## What it does

Joins **POSE-LAN** as `192.168.50.20`, listens for laptop UDP JSON on port
**9100**, and paints a fixed front-facing view on a 16×16 WS2812 panel.

```text
Laptop  ── JSON + 5 targets :9100 ──►  ESP32  ──►  WS2812 16×16
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

The body remains static and all five points are projected directly from x/y
coordinates. The ESP32 ignores `angle` and z-depth, so screen rotation does not
change the image.

```json
{"type":"heartbeat","t_send_ms":1784185200623}
```

Duplicate or older `frame_id` values are ignored. After 1 s without a packet
the panel blanks; while waiting for the first frame an idle chase runs.

## Wiring

| ESP32-S3 | Panel |
|-----------|-------|
| GPIO 4 | top-left 8×8 DIN |
| GPIO 5 | top-right 8×8 DIN |
| GPIO 6 | bottom-left 8×8 DIN |
| GPIO 7 | bottom-right 8×8 DIN |
| GND | all panel and 5 V supply grounds |

Power the matrix from a stout **5 V** supply (not the ESP32 5 V pin). Common
ground is required. The sketch caps FastLED at 2 A and brightness 40.

## Config to edit before flash

Near the top of [`outpost_display.ino`](outpost_display/outpost_display.ino):

| Symbol | Default | Notes |
|--------|---------|--------|
| `WIFI_SSID` | `POSE-LAN` | Must match the laptop AP / router |
| `WIFI_PASS` | `outpost123` | Change to your WPA2 passphrase |
| `WIFI_IP` | `192.168.50.20` | Reserved ESP32 address from PLAN.md |
| `UDP_PORT` | `9100` | `OUTPOST_ESP32_PORT` |
| `SERPENTINE` | `false` | Use `true` if each 8×8 panel zigzags |
| `LED_POWER_MA` | `2000` | Match the safe output of your supply |

## Flash with Arduino IDE

1. Install Arduino IDE 2.
2. In **Boards Manager**, install **esp32 by Espressif Systems**.
3. In **Library Manager**, install **FastLED**.
4. Open `file-for-esp32/outpost_display/outpost_display.ino`.
5. Select **Tools → Board → esp32 → ESP32S3 Dev Module**.
6. Set **Tools → USB CDC On Boot → Enabled**. This may not be your default, so
   select it explicitly.
7. Connect the ESP32-S3 over its data-capable USB connector and select its port
   under **Tools → Port**.
8. Click **Upload**.

If upload remains at `Connecting...`, hold **BOOT**, tap **RESET**, release
**BOOT** when writing starts, and retry. Open Serial Monitor at **115200 baud**
after upload.

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

You should see the dim cyan body plus all five colored target points in a fixed
front-facing view.

## Safety

A spinning LED panel is a mechanical hazard. Start at low RPM, secure wiring
(slip ring or careful cable management), and keep hands clear of the sweep.
