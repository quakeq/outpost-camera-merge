/*
 * Outpost Pico stepper controller
 * -------------------------------
 * Flash with Arduino IDE + "Raspberry Pi Pico" (Earle Philhower core)
 * or equivalent Arduino-Pico toolchain. USB CDC appears as /dev/ttyACM0.
 *
 * Laptop protocol (see outpost motor.py):
 *   Host writes:  ?\n
 *   Pico replies: pos=<int> target=<int>\n
 *
 * Optional host commands:
 *   pos=<int>\n      force current position counter
 *   enable\n / disable\n
 *
 * Assumes NEMA17 @ 1/16 microstepping => 3200 microsteps / revolution.
 * Wire STEP / DIR / EN to your driver; set MICROSTEP jumpers to 1/16.
 */

#include <Arduino.h>

// --- pin map (change to match your wiring) ---
static const uint8_t PIN_STEP = 2;
static const uint8_t PIN_DIR = 3;
static const uint8_t PIN_EN = 4;  // active LOW on most A4988/DRV8825 boards

static const uint32_t STEP_PULSE_US = 4;
static const uint32_t STEPS_PER_REV = 3200;

// Speed tuning (delay between step half-cycles; lower = faster)
static const uint32_t MIN_DELAY_MICROS = 200;   // top speed
static const uint32_t MAX_DELAY_MICROS = 2000;  // startup torque
static const uint32_t ACCEL_STEP = 5;           // ramp smoothness

static int32_t position_steps = 0;
static bool motor_enabled = false;
static bool decelerating = false;
static uint32_t current_delay_micros = MAX_DELAY_MICROS;
static uint32_t last_step_us = 0;

static String line_buf;

static void set_driver_enabled(bool on) {
  digitalWrite(PIN_EN, on ? LOW : HIGH);
}

static void set_enabled(bool on) {
  if (on) {
    decelerating = false;
    current_delay_micros = MAX_DELAY_MICROS;
    last_step_us = micros();
    motor_enabled = true;
    set_driver_enabled(true);
    return;
  }
  if (motor_enabled) {
    decelerating = true;
  }
}

static void step_once() {
  digitalWrite(PIN_STEP, HIGH);
  delayMicroseconds(STEP_PULSE_US);
  digitalWrite(PIN_STEP, LOW);
  position_steps = (position_steps + 1) % STEPS_PER_REV;
}

static void service_motion() {
  if (!motor_enabled && !decelerating) {
    return;
  }

  const uint32_t now = micros();
  const uint32_t interval = current_delay_micros * 2;
  if ((uint32_t)(now - last_step_us) < interval) {
    return;
  }
  last_step_us = now;
  step_once();

  if (decelerating) {
    if (current_delay_micros < MAX_DELAY_MICROS) {
      current_delay_micros += ACCEL_STEP;
      if (current_delay_micros > MAX_DELAY_MICROS) {
        current_delay_micros = MAX_DELAY_MICROS;
      }
    } else {
      motor_enabled = false;
      decelerating = false;
      set_driver_enabled(false);
    }
    return;
  }

  if (motor_enabled && current_delay_micros > MIN_DELAY_MICROS) {
    if (current_delay_micros > MIN_DELAY_MICROS + ACCEL_STEP) {
      current_delay_micros -= ACCEL_STEP;
    } else {
      current_delay_micros = MIN_DELAY_MICROS;
    }
  }
}

static void reply_state() {
  Serial.print(F("pos="));
  Serial.print(position_steps);
  Serial.print(F(" target="));
  Serial.println(position_steps);
}

static void handle_line(String line) {
  line.trim();
  if (line.length() == 0) {
    return;
  }
  if (line.equals("?") || line.equalsIgnoreCase("status")) {
    reply_state();
    return;
  }
  if (line.equalsIgnoreCase("enable")) {
    set_enabled(true);
    reply_state();
    return;
  }
  if (line.equalsIgnoreCase("disable") || line.equalsIgnoreCase("stop")) {
    set_enabled(false);
    reply_state();
    return;
  }
  if (line.startsWith("pos=")) {
    position_steps = line.substring(4).toInt() % (int32_t)STEPS_PER_REV;
    if (position_steps < 0) {
      position_steps += STEPS_PER_REV;
    }
    reply_state();
    return;
  }
  // Unknown command: still answer in protocol shape so the laptop can recover.
  reply_state();
}

void setup() {
  pinMode(PIN_STEP, OUTPUT);
  pinMode(PIN_DIR, OUTPUT);
  pinMode(PIN_EN, OUTPUT);

  digitalWrite(PIN_STEP, LOW);
  digitalWrite(PIN_DIR, HIGH);
  set_driver_enabled(true);
  set_enabled(true);

  Serial.begin(115200);
  while (!Serial && millis() < 2000) {
    // USB CDC enumerate
  }
}

void loop() {
  while (Serial.available() > 0) {
    const char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (line_buf.length() > 0) {
        handle_line(line_buf);
        line_buf = "";
      }
    } else if (line_buf.length() < 64) {
      line_buf += c;
    }
  }
  service_motion();
}
