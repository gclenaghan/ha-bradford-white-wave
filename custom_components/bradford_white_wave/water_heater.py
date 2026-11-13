"""Water heater platform for Bradford White Wave."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from bradford_white_wave_client import (
    BradfordWhiteAuthError,
    BradfordWhiteConnectError,
    BradfordWhiteMode,
)

from .const import DOMAIN, MODE_BW_TO_HA, MODE_HA_TO_BW
from .coordinator import BradfordWhiteWaveStatusCoordinator
from .entity import BradfordWhiteWaveStatusEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the water heater platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: BradfordWhiteWaveStatusCoordinator = data.status_coordinator

    entities: list[BradfordWhiteWaveWaterHeater] = []

    for mac, device in coordinator.data.items():
        device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=device.friendly_name,
            manufacturer="Bradford White",
            model=device.appliance_type,
            serial_number=device.serial_number,
        )

        entities.append(BradfordWhiteWaveWaterHeater(coordinator, mac, device_info))

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

    def __init__(
        self,
        coordinator: BradfordWhiteWaveStatusCoordinator,
        mac_address: str,
        info: DeviceInfo,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, mac_address, info)
        self._attr_unique_id = mac_address
        self._attr_name = None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self.device:
            return self.device.setpoint_fahrenheit
        return None

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return 100

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return 140

    @property
    def current_operation(self) -> str | None:
        """Return current operation mode."""
        if not self.device or self.device.heating_mode is None:
            return None
        return MODE_BW_TO_HA.get(self.device.heating_mode)

    @property
    def operation_list(self) -> list[str]:
        """List of available operation modes."""
        return list(MODE_HA_TO_BW.keys())

    async def _async_execute_control(self, action: Callable[[], Awaitable[Any]]) -> None:
        """Execute a write action, trigger fast polling, and wrap client errors."""
        try:
            await action()
        except BradfordWhiteAuthError as err:
            self.coordinator.entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                f"Authentication failed while controlling water heater: {err}"
            ) from err
        except BradfordWhiteConnectError as err:
            raise HomeAssistantError(
                f"Failed to communicate with Bradford White Wave: {err}"
            ) from err

        self.coordinator.shared_data["last_api_set_datetime"] = datetime.now()
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get("temperature")
        if temp is not None:
            await self._async_execute_control(
                lambda: self.coordinator.client.set_temperature(self.mac_address, int(temp))
            )

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        bw_mode = MODE_HA_TO_BW.get(operation_mode)
        if bw_mode is not None:
            await self._async_execute_control(
                lambda: self.coordinator.client.set_mode(self.mac_address, bw_mode)
            )

    @property
    def is_away_mode_on(self) -> bool | None:
        """Return true if away mode is on."""
        if not self.device:
            return None
        return self.device.heating_mode is BradfordWhiteMode.VACATION

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        await self._async_execute_control(
            lambda: self.coordinator.client.set_mode(self.mac_address, BradfordWhiteMode.VACATION)
        )

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        await self._async_execute_control(
            lambda: self.coordinator.client.set_mode(self.mac_address, BradfordWhiteMode.HEAT_PUMP)
        )
