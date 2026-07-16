#pragma once

#include <stdint.h>

// --- Wi-Fi (POSE-LAN station mode; matches outpost PLAN.md) ---
static const char *WIFI_SSID = "POSE-LAN";
static const char *WIFI_PASS = "outpost123";  // change to match your AP

static const uint8_t WIFI_IP[4] = {192, 168, 50, 20};
static const uint8_t WIFI_GW[4] = {192, 168, 50, 1};
static const uint8_t WIFI_MASK[4] = {255, 255, 255, 0};

// Laptop → ESP32 display packets (JSON angle + five pose targets)
static const uint16_t UDP_PORT = 9100;

// --- WS2812 panel (16×16, diameter-mounted on shaft) ---
#ifndef LED_PIN
#define LED_PIN 2
#endif
#define PANEL_W 16
#define PANEL_H 16
#define PANEL_PIXELS (PANEL_W * PANEL_H)
#define LED_BRIGHTNESS 40

// Blank the panel if no UDP packet arrives within this window.
static const uint32_t RX_TIMEOUT_MS = 1000;

// Pose target mapping and rotating-slice thickness, in LED-pitch units.
static const float TARGET_X_SCALE = 14.0f;
static const float TARGET_Z_SCALE = 10.0f;
static const float TARGET_SLICE_HALF_WIDTH = 1.25f;
