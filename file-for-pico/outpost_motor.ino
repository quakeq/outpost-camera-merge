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

static const bool EN_ACTIVE_LOW = true;
static const uint32_t STEP_PULSE_US = 4;
static const uint32_t STEPS_PER_REV = 3200;
static const uint32_t START_STEP_RATE = 800;
static const uint32_t FAST_STEP_RATE = 12500;  // ~234 RPM at 1/16 microstepping
static const uint32_t RAMP_TIME_US = 2000000;  // ramp up so the motor does not stall

static int32_t position_steps = 0;
static bool motor_enabled = false;
static uint32_t last_step_us = 0;
static uint32_t ramp_start_us = 0;

static String line_buf;

static void set_enabled(bool on) {
  if (on && !motor_enabled) {
    ramp_start_us = micros();
    last_step_us = ramp_start_us;
  }
  motor_enabled = on;
  const bool level = EN_ACTIVE_LOW ? !on : on;
  digitalWrite(PIN_EN, level ? HIGH : LOW);
}

static uint32_t step_interval_us(uint32_t now) {
  uint32_t elapsed = now - ramp_start_us;
  if (elapsed > RAMP_TIME_US) {
    elapsed = RAMP_TIME_US;
  }
  const uint32_t rate =
      START_STEP_RATE +
      (uint32_t)(((uint64_t)(FAST_STEP_RATE - START_STEP_RATE) * elapsed) /
                 RAMP_TIME_US);
  return 1000000 / rate;
}

static void step_once() {
  digitalWrite(PIN_STEP, HIGH);
  delayMicroseconds(STEP_PULSE_US);
  digitalWrite(PIN_STEP, LOW);
  position_steps = (position_steps + 1) % STEPS_PER_REV;
}

static void service_motion() {
  if (!motor_enabled) {
    return;
  }
  const uint32_t now = micros();
  if ((uint32_t)(now - last_step_us) < step_interval_us(now)) {
    return;
  }
  last_step_us = now;
  step_once();
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
  digitalWrite(PIN_DIR, HIGH);  // fixed direction: change to LOW to reverse
  delayMicroseconds(2);
  set_enabled(true);

  Serial.begin(115200);
  while (!Serial && millis() < 2000) {
    // USB CDC enumerate
  }
  // A fresh flash ramps up and then spins continuously in one direction.
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
