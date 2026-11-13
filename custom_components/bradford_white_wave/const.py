"""Constants for the Bradford White Wave integration."""

from __future__ import annotations

from datetime import timedelta

from bradford_white_wave_client import BradfordWhiteMode
from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_OFF,
)

DOMAIN = "bradford_white_wave"
CONF_REFRESH_TOKEN = "refresh_token"

# Intervals
REGULAR_INTERVAL = timedelta(seconds=60)
FAST_INTERVAL = timedelta(seconds=10)
ENERGY_USAGE_INTERVAL = timedelta(minutes=5)

# Mode mappings
MODE_HA_TO_BW: dict[str, BradfordWhiteMode] = {
    STATE_ECO: BradfordWhiteMode.HYBRID,
    STATE_ELECTRIC: BradfordWhiteMode.ELECTRIC,
    STATE_HEAT_PUMP: BradfordWhiteMode.HEAT_PUMP,
    STATE_HIGH_DEMAND: BradfordWhiteMode.HYBRID_PLUS,
    STATE_OFF: BradfordWhiteMode.VACATION,
}

MODE_BW_TO_HA: dict[BradfordWhiteMode, str] = {
    BradfordWhiteMode.ELECTRIC: STATE_ELECTRIC,
    BradfordWhiteMode.HEAT_PUMP: STATE_HEAT_PUMP,
    BradfordWhiteMode.HYBRID_PLUS: STATE_HIGH_DEMAND,
    BradfordWhiteMode.HYBRID: STATE_ECO,
    BradfordWhiteMode.VACATION: STATE_OFF,
}

# Native Bradford White operation mode options for the select entity
SELECT_OPTIONS_TO_BW: dict[str, BradfordWhiteMode] = {
    "hybrid": BradfordWhiteMode.HYBRID,
    "hybrid_plus": BradfordWhiteMode.HYBRID_PLUS,
    "heat_pump": BradfordWhiteMode.HEAT_PUMP,
    "electric": BradfordWhiteMode.ELECTRIC,
    "vacation": BradfordWhiteMode.VACATION,
}

BW_TO_SELECT_OPTIONS: dict[BradfordWhiteMode, str] = {
    mode: option for option, mode in SELECT_OPTIONS_TO_BW.items()
}
