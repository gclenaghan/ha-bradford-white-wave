"""Sensor platform for Bradford White Wave."""

from __future__ import annotations

import contextlib
import logging

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ENABLED_ENERGY_VIEWS, BradfordWhiteWaveEnergyCoordinator
from .entity import BradfordWhiteWaveEnergyEntity, build_device_info

_LOGGER = logging.getLogger(__name__)

ENERGY_TYPES: tuple[str, ...] = ("total_energy", "heat_pump_energy", "element_energy")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: BradfordWhiteWaveEnergyCoordinator = data.energy_coordinator
    status_coordinator = data.status_coordinator

    entities: list[BradfordWhiteWaveEnergySensor] = []

    for mac, device in status_coordinator.data.items():
        device_info = build_device_info(mac, device)

        for view_type in ENABLED_ENERGY_VIEWS:
            for energy_type in ENERGY_TYPES:
                entities.append(
                    BradfordWhiteWaveEnergySensor(
                        coordinator,
                        mac,
                        device_info,
                        view_type.value,
                        energy_type,
                    )
                )

    async_add_entities(entities)


class BradfordWhiteWaveEnergySensor(BradfordWhiteWaveEnergyEntity, RestoreSensor):
    """Energy Sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        coordinator: BradfordWhiteWaveEnergyCoordinator,
        mac_address: str,
        info: DeviceInfo,
        view_type: str,
        energy_type: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, mac_address, info)
        self._view_type = view_type
        self._energy_type = energy_type

        self._attr_unique_id = f"{mac_address}_{view_type}_{energy_type}"
        self._attr_translation_key = f"{view_type}_{energy_type}"

        self._cached_value: float | None = None

    def _get_raw_value(self) -> float | None:
        """Get the raw value from the coordinator."""
        if not self.device_data:
            return None

        view_data = self.device_data.get(self._view_type)
        if not view_data:
            return None

        latest_usage = view_data[0]
        return getattr(latest_usage, self._energy_type, None)

    def _update_cached_value(self, raw: float | None) -> None:
        """Update cached energy value while filtering minor downward API jitter."""
        if raw is None:
            return
        if self._cached_value is None:
            self._cached_value = raw
        elif raw < self._cached_value:
            # This API sometimes returns a slightly lower value even in between resets;
            # filter these out unless the drop is significant and likely a period reset.
            if raw < 0.1 or raw < self._cached_value * 0.5:
                self._cached_value = raw
        else:
            self._cached_value = raw

    async def async_added_to_hass(self) -> None:
        """Restore last known value on startup before evaluating initial coordinator data."""
        await super().async_added_to_hass()
        if (
            last_data := await self.async_get_last_sensor_data()
        ) is not None and last_data.native_value is not None:
            with contextlib.suppress(TypeError, ValueError):
                self._cached_value = float(last_data.native_value)
        self._update_cached_value(self._get_raw_value())

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_cached_value(self._get_raw_value())
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> float | None:
        """Return the value."""
        if self._cached_value is None:
            self._update_cached_value(self._get_raw_value())

        return self._cached_value

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.device_data is not None
