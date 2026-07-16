/*
 * Circle test — four 8x8 WS2812B panels as one 16x16 display
 * ------------------------------------------------------------
 * Board: ESP32S3 Dev Module, USB CDC On Boot = Enabled
 * Library: FastLED
 *
 * Draws a circle centered on the combined panel. Use this to verify
 * wiring, panel order, and serpentine orientation before flashing
 * outpost_display.
 *
 * Four independent 8x8 WS2812B panels arranged:
 *   [GPIO4][GPIO5]
 *   [GPIO6][GPIO7]
 *
 * Use a stout 5 V supply; common its GND with ESP32 GND.
 */

#include <Arduino.h>
#include <FastLED.h>
#include <math.h>

#define PANEL 64
#define STRIPS 4
#define TOTAL (PANEL * STRIPS)
#define PANEL_W 16
#define PANEL_H 16

static const bool SERPENTINE = false;
static const uint8_t LED_BRIGHTNESS = 40;
static const uint16_t LED_POWER_MA = 2000;

// Circle center (middle of 16x16) and radius in LED units.
static const float CIRCLE_CX = 7.5f;
static const float CIRCLE_CY = 7.5f;
static const float CIRCLE_RADIUS = 5.0f;
static const float CIRCLE_THICKNESS = 0.75f;

CRGB leds[TOTAL];

// Map (x,y) in the 16x16 square to the matching 8x8 panel.
// Physical layout: [0][1]
//                  [2][3]
static uint16_t xy(uint8_t x, uint8_t y) {
  const uint8_t panel = (y / 8) * 2 + (x / 8);
  uint8_t px = x % 8;
  const uint8_t py = y % 8;
  if (SERPENTINE && (py & 1)) {
    px = 7 - px;
  }
  return panel * PANEL + py * 8 + px;
}

static void draw_circle() {
  FastLED.clear(true);

  for (uint8_t y = 0; y < PANEL_H; y++) {
    for (uint8_t x = 0; x < PANEL_W; x++) {
      const float dx = (float)x - CIRCLE_CX;
      const float dy = (float)y - CIRCLE_CY;
      const float dist = sqrtf(dx * dx + dy * dy);
      if (fabsf(dist - CIRCLE_RADIUS) <= CIRCLE_THICKNESS) {
        leds[xy(x, y)] = CRGB(0, 180, 255);
      }
    }
  }

  // Small center dot to confirm alignment.
  leds[xy(7, 7)] = CRGB(255, 255, 255);
  leds[xy(8, 7)] = CRGB(255, 255, 255);
  leds[xy(7, 8)] = CRGB(255, 255, 255);
  leds[xy(8, 8)] = CRGB(255, 255, 255);
}

void setup() {
  Serial.begin(115200);
  delay(200);

  FastLED.addLeds<WS2812B, 4, GRB>(leds, 0 * PANEL, PANEL);
  FastLED.addLeds<WS2812B, 6, GRB>(leds, 1 * PANEL, PANEL);
  FastLED.addLeds<WS2812B, 5, GRB>(leds, 2 * PANEL, PANEL);
  FastLED.addLeds<WS2812B, 7, GRB>(leds, 3 * PANEL, PANEL);
  FastLED.setMaxPowerInVoltsAndMilliamps(5, LED_POWER_MA);
  FastLED.setBrightness(LED_BRIGHTNESS);

  draw_circle();
  FastLED.show();

  Serial.println("circle_test ready — cyan ring, white center cross");
}

void loop() {
  // Static image; nothing to update.
}
