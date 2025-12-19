"""Constants for the Bradford White Wave integration."""
from datetime import timedelta

DOMAIN = "bradford_white_wave"

# Intervals
REGULAR_INTERVAL = timedelta(seconds=60)
FAST_INTERVAL = timedelta(seconds=10)
ENERGY_USAGE_INTERVAL = timedelta(minutes=5)

# Mode mappings
from bradford_white_wave_client.models import BradfordWhiteMode
from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_OFF,
)

MODE_HA_TO_BW = {
    STATE_ECO: BradfordWhiteMode.HYBRID,
    STATE_ELECTRIC: BradfordWhiteMode.ELECTRIC,
    STATE_HEAT_PUMP: BradfordWhiteMode.HEAT_PUMP,
    STATE_HIGH_DEMAND: BradfordWhiteMode.HYBRID_PLUS,
    STATE_OFF: BradfordWhiteMode.VACATION,
}

MODE_BW_TO_HA = {
    BradfordWhiteMode.ELECTRIC: STATE_ELECTRIC,
    BradfordWhiteMode.HEAT_PUMP: STATE_HEAT_PUMP,
    BradfordWhiteMode.HYBRID_PLUS: STATE_HIGH_DEMAND,
    BradfordWhiteMode.HYBRID: STATE_ECO,
    BradfordWhiteMode.VACATION: STATE_OFF,
}
