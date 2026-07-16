#include "led_driver.h"

#include <FastLED.h>

static CRGB leds[PANEL_PIXELS];

static inline uint16_t serpentine_index(uint8_t col, uint8_t row) {
  if (row & 1) {
    return (uint16_t)row * PANEL_W + (PANEL_W - 1 - col);
  }
  return (uint16_t)row * PANEL_W + col;
}

void led_driver_begin() {
  FastLED.addLeds<WS2812B, LED_PIN, GRB>(leds, PANEL_PIXELS);
  FastLED.setBrightness(LED_BRIGHTNESS);
  led_driver_clear();
}

void led_driver_clear() {
  fill_solid(leds, PANEL_PIXELS, CRGB::Black);
  FastLED.show();
}

void led_driver_show_rgb888(const uint8_t *rgb888) {
  for (uint8_t row = 0; row < PANEL_H; row++) {
    for (uint8_t col = 0; col < PANEL_W; col++) {
      const size_t off = ((size_t)row * PANEL_W + col) * 3;
      leds[serpentine_index(col, row)] =
          CRGB(rgb888[off], rgb888[off + 1], rgb888[off + 2]);
    }
  }
  FastLED.show();
}
