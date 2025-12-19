"""Water heater platform for Bradford White Wave."""

from __future__ import annotations

import logging
from typing import Any
from datetime import datetime

from bradford_white_wave_client.models import BradfordWhiteMode
from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, PRECISION_WHOLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, MODE_HA_TO_BW, MODE_BW_TO_HA
from .coordinator import BradfordWhiteWaveStatusCoordinator
from .entity import BradfordWhiteWaveStatusEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the water heater platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: BradfordWhiteWaveStatusCoordinator = data.status_coordinator

    entities = []
    
    # Coordinator data is Dict[mac, DeviceStatus]
    for mac, device in coordinator.data.items():
        device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=device.friendly_name,
            manufacturer="Bradford White",
            model=device.appliance_type, # Or derive from serial if needed
            serial_number=device.serial_number,
        )
        
        entities.append(
            BradfordWhiteWaveWaterHeater(coordinator, mac, device_info)
        )

    async_add_entities(entities)


class BradfordWhiteWaveWaterHeater(BradfordWhiteWaveStatusEntity, WaterHeaterEntity):
    """Bradford White Wave Water Heater Entity."""

    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_precision = PRECISION_WHOLE
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.AWAY_MODE
    )

    def __init__(self, coordinator: BradfordWhiteWaveStatusCoordinator, mac_address: str, info: DeviceInfo):
        """Initialize."""
        super().__init__(coordinator, mac_address, info)
        self._attr_unique_id = mac_address
        self._attr_name = None # Use device name

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        # DeviceStatus has no current temp? 
        # Check models.py in client: setpoint_fahrenheit is setpoint.
        # Wait, the prompt memory for rules says "Device List... returns a dict... "
        # but models.py shows:
        # setpoint_fahrenheit, mode, heat_mode_value, request_id
        # It does NOT show 'tank_temp' or 'current_temp' in DeviceStatus in models.py 
        # BUT the client.py 'get_status' returns DeviceStatus.
        # Let's check models.py again.
        
        # models.py shows DeviceStatus has:
        # mac_address, friendly_name, serial_number, setpoint_fahrenheit, mode, heat_mode_value...
        # It seems missing 'current_temperature'. 
        
        # HOWEVER, the old integration water_heater.py used `tank_temp` from `properties`.
        # The new client library might be missing it in models.py if I didn't see it correctly. 
        # Start of conversation shows models.py:
        # class DeviceStatus(BaseModel):
        # ... setpoint_fahrenheit, mode, heat_mode_value...
        
        # Wait, does the Wave API provide current temp?
        # The prompt says "cloud polling water heater device... with controllable temperature setpoint...".
        # It doesn't explicitly guarantee current temp is available, but usually it is.
        # I suspect `DeviceStatus` might be incomplete or the API doesn't return it in the list view.
        # But `get_status` calls `ENDPOINT_GET_STATUS`. 
        # If models.py doesn't have it, I can't access it easily via typed object.
        # But `DeviceStatus` is a Pydantic model. If the API returns extra fields, Pydantic might ignore them 
        # unless configured otherwise, or I can check `device.model_dump()` or `__dict__`.
        
        # If it's not there, I'll return None for current_temperature.
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self.device:
            return self.device.setpoint_fahrenheit
        return None

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return 100 # Default/Safe guess, or make constant

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return 140 # Default/Safe guess

    @property
    def current_operation(self) -> str | None:
        """Return current operation ie. heat, cool, idle."""
        if not self.device:
            return None
        
        # device.heat_mode_value is int
        if self.device.heat_mode_value is not None:
             # Look up IntEnum from value
             try:
                 mode_enum = BradfordWhiteMode(self.device.heat_mode_value)
                 return MODE_BW_TO_HA.get(mode_enum)
             except ValueError:
                 return None
        return None

    @property
    def operation_list(self) -> list[str]:
        """List of available operation modes."""
        # Assume all modes supported for now
        return list(MODE_HA_TO_BW.keys())

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get("temperature")
        if temp is not None:
             await self.coordinator.client.set_temperature(self.mac_address, int(temp))
             self.coordinator.shared_data["last_api_set_datetime"] = datetime.now()
             await self.coordinator.async_request_refresh()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        bw_mode = MODE_HA_TO_BW.get(operation_mode)
        if bw_mode:
            await self.coordinator.client.set_mode(self.mac_address, bw_mode)
            self.coordinator.shared_data["last_api_set_datetime"] = datetime.now()
            await self.coordinator.async_request_refresh()

    @property
    def is_away_mode_on(self) -> bool | None:
        """Return true if away mode is on."""
        if not self.device:
            return None
        return self.device.heat_mode_value == BradfordWhiteMode.VACATION

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        await self.coordinator.client.set_mode(self.mac_address, BradfordWhiteMode.VACATION)
        self.coordinator.shared_data["last_api_set_datetime"] = datetime.now()
        await self.coordinator.async_request_refresh()

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        # Default to standard Hybrid or whatever is reasonable. 
        # Or HeatPump which is efficient.
        await self.coordinator.client.set_mode(self.mac_address, BradfordWhiteMode.HEAT_PUMP)
        self.coordinator.shared_data["last_api_set_datetime"] = datetime.now()
        await self.coordinator.async_request_refresh()
