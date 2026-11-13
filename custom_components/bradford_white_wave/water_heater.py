"""Water heater platform for Bradford White Wave."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from bradford_white_wave_client import (
    BradfordWhiteAuthError,
    BradfordWhiteConnectError,
    BradfordWhiteMode,
)
from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import MODE_BW_TO_HA, MODE_HA_TO_BW
from .coordinator import BradfordWhiteConfigEntry, BradfordWhiteWaveStatusCoordinator
from .entity import BradfordWhiteWaveStatusEntity, build_device_info

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BradfordWhiteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the water heater platform."""
    coordinator = entry.runtime_data.status_coordinator

    entities = [
        BradfordWhiteWaveWaterHeater(coordinator, mac, build_device_info(mac, device))
        for mac, device in coordinator.data.items()
    ]

    async_add_entities(entities)


class BradfordWhiteWaveWaterHeater(BradfordWhiteWaveStatusEntity, WaterHeaterEntity):
    """Bradford White Wave Water Heater Entity."""

    _attr_name = None
    _attr_native_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_precision = PRECISION_WHOLE
    _attr_target_temperature_step = 1.0
    _attr_min_temp = 100.0
    _attr_max_temp = 140.0
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
        self._last_non_vacation_mode: BradfordWhiteMode = BradfordWhiteMode.HYBRID
        self._record_non_vacation_mode()

    @callback
    def _record_non_vacation_mode(self) -> None:
        """Remember the most recent active mode so away-mode off can restore it."""
        if (
            self.device is not None
            and self.device.heating_mode is not None
            and self.device.heating_mode is not BradfordWhiteMode.VACATION
        ):
            self._last_non_vacation_mode = self.device.heating_mode

    @callback
    def _handle_coordinator_update(self) -> None:
        """Track active non-vacation mode across coordinator updates."""
        self._record_non_vacation_mode()
        super()._handle_coordinator_update()

    @property
    def native_target_temperature(self) -> float | None:
        """Return the target temperature in Fahrenheit."""
        if self.device and self.device.setpoint_fahrenheit is not None:
            return float(self.device.setpoint_fahrenheit)
        return None

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

    async def _async_execute_control[ResultT](
        self, action: Callable[[], Awaitable[ResultT]]
    ) -> ResultT:
        """Execute a write action and wrap client errors."""
        try:
            return await action()
        except BradfordWhiteAuthError as err:
            self.coordinator.entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                f"Authentication failed while controlling water heater: {err}"
            ) from err
        except BradfordWhiteConnectError as err:
            raise HomeAssistantError(
                f"Failed to communicate with Bradford White Wave: {err}"
            ) from err

    async def _async_set_bw_mode(self, bw_mode: BradfordWhiteMode) -> None:
        """Send a mode change to the API and apply optimistic state."""
        if bw_mode is not BradfordWhiteMode.VACATION:
            self._last_non_vacation_mode = bw_mode

        response = await self._async_execute_control(
            lambda: self.coordinator.client.set_mode(self.mac_address, bw_mode)
        )
        applied_mode = bw_mode
        if response.actual_mode is not None:
            try:
                applied_mode = BradfordWhiteMode(response.actual_mode)
            except ValueError:
                applied_mode = bw_mode

        if applied_mode is not BradfordWhiteMode.VACATION:
            self._last_non_vacation_mode = applied_mode

        self.coordinator.apply_optimistic_mode(self.mac_address, applied_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return

        target_temp = round(float(temp))
        if not self._attr_min_temp <= target_temp <= self._attr_max_temp:
            raise ServiceValidationError(
                f"Target temperature {target_temp}°F is outside valid range "
                f"({int(self._attr_min_temp)}-{int(self._attr_max_temp)}°F)"
            )

        response = await self._async_execute_control(
            lambda: self.coordinator.client.set_temperature(self.mac_address, target_temp)
        )
        applied_temp = (
            response.actual_temperature if response.actual_temperature is not None else target_temp
        )
        self.coordinator.apply_optimistic_temperature(self.mac_address, applied_temp)

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        bw_mode = MODE_HA_TO_BW.get(operation_mode)
        if bw_mode is None:
            raise ServiceValidationError(f"Unsupported operation mode: {operation_mode}")

        await self._async_set_bw_mode(bw_mode)

    @property
    def is_away_mode_on(self) -> bool | None:
        """Return true if away mode is on."""
        if not self.device:
            return None
        return self.device.heating_mode is BradfordWhiteMode.VACATION

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        self._record_non_vacation_mode()
        await self._async_set_bw_mode(BradfordWhiteMode.VACATION)

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off, restoring the prior active mode."""
        await self._async_set_bw_mode(self._last_non_vacation_mode)
