# Pico stepper firmware for Outpost

Flash [`outpost_motor.ino`](outpost_motor.ino) to a Raspberry Pi Pico with the
Arduino IDE (Earle Philhower "Raspberry Pi Pico" board package).

## Wiring (defaults in the sketch)

| Pico GPIO | Driver        |
|-----------|---------------|
| GP2       | STEP          |
| GP3       | DIR           |
| GP4       | EN (active low) |

Set driver microstep jumpers to **1/16**. Power the motor from VM (not USB alone).

## Serial protocol (matches laptop `motor.py`)

| Host sends     | Pico replies              |
|----------------|---------------------------|
| `?\n`          | `pos=<n> target=<m>\n`    |
| `target=1600\n`| same status line          |
| `enable\n` / `disable\n` | status line     |

After flash, the sketch sets `target=1600` (half rev) so the shaft should move
once. Then the laptop can poll with:

```bash
OUTPOST_MOTOR_PORT=/dev/ttyACM0 python -m outpost.main --require-motor
```

Quick check:

```bash
python -c "
import serial
s = serial.Serial('/dev/ttyACM0', 115200, timeout=0.5)
s.write(b'?\\n'); s.flush()
print(repr(s.readline()))
"
```

Expect `b'pos=... target=...\\n'`, not `b'?'`.
