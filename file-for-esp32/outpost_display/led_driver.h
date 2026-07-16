#pragma once

#include <stdint.h>
#include <stddef.h>
#include "config.h"

void led_driver_begin();
void led_driver_clear();

// Show RGB888 framebuffer: PANEL_H rows × PANEL_W cols, 3 bytes RGB each.
void led_driver_show_rgb888(const uint8_t *rgb888);
