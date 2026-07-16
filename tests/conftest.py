from __future__ import annotations

import pytest

from outpost.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        esp32_host="127.0.0.1",
        min_good_landmarks=2,
        max_frame_age_ms=150,
    )
