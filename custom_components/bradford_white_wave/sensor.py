"""Sensor platform for Bradford White Wave."""

from __future__ import annotations

import logging
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .coordinator import BradfordWhiteWaveEnergyCoordinator
from .entity import BradfordWhiteWaveEnergyEntity

_LOGGER = logging.getLogger(__name__)

VIEW_TYPES = ["weekly", "monthly"]
ENERGY_TYPES = ["total_energy", "heat_pump_energy", "element_energy"]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: BradfordWhiteWaveEnergyCoordinator = data.energy_coordinator
    status_coordinator = data.status_coordinator

    entities = []

    # Use status coordinator to get device info (friendly name etc)
    # Energy coordinator keys should match.
    for mac, device in status_coordinator.data.items():
        device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=device.friendly_name,
            manufacturer="Bradford White",
            model=device.appliance_type,
            serial_number=device.serial_number,
        )

        for view_type in VIEW_TYPES:
            for energy_type in ENERGY_TYPES:
                entities.append(
                    BradfordWhiteWaveEnergySensor(
                        coordinator,
                        mac,
                        device_info,
                        view_type,
                        energy_type,
                        device.friendly_name,
                    )
                )

    async_add_entities(entities)


class BradfordWhiteWaveEnergySensor(BradfordWhiteWaveEnergyEntity, SensorEntity):
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
        device_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, mac_address, info)
        self._view_type = view_type
        self._energy_type = energy_type

        # Format name: "DeviceName Daily Total Energy"
        pretty_view = view_type.title()
        pretty_type = energy_type.replace("_", " ").title()

        self._attr_unique_id = f"{mac_address}_{view_type}_{energy_type}"
        self._attr_has_entity_name = True
        self._attr_translation_key = f"{view_type}_{energy_type}"
        self._attr_name = f"{pretty_view} {pretty_type}"

        self._cached_value: float | None = None

    def _get_raw_value(self) -> float | None:
        """Get the raw value from the coordinator."""
        if not self.device_data:
            return None

        view_data = self.device_data.get(self._view_type)
        if not view_data:
            return None

        # Latest data is returned first
        latest_usage = view_data[0]

        # Get the field
        return getattr(latest_usage, self._energy_type, None)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        raw = self._get_raw_value()

        if raw is not None:
            if self._cached_value is None:
                self._cached_value = raw
            elif raw < self._cached_value:
                # This API sometimes returns a slightly lower value even in between resets,
                # we will filter these out unless the drop is significant and likely to be a reset
                if raw < 0.1 or raw < self._cached_value * 0.5:
                    self._cached_value = raw
                else:
                    # Treat as jitter, ignore the drop (clamp to previous)
                    pass
            else:
                self._cached_value = raw

        super()._handle_coordinator_update()

    @property
    def native_value(self) -> float | None:
        """Return the value."""
        if self._cached_value is None:
            self._cached_value = self._get_raw_value()

        return self._cached_value

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.device_data is not None
