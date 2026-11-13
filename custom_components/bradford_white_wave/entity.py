"""Base entity for Bradford White Wave."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from bradford_white_wave_client import DeviceStatus, EnergyUsage

from .const import DOMAIN
from .coordinator import (
    BradfordWhiteWaveEnergyCoordinator,
    BradfordWhiteWaveStatusCoordinator,
)


def build_device_info(mac_address: str, device: DeviceStatus) -> DeviceInfo:
    """Build standard Home Assistant DeviceInfo from a Bradford White Wave device."""
    return DeviceInfo(
        identifiers={(DOMAIN, mac_address)},
        name=device.friendly_name,
        manufacturer="Bradford White",
        model=device.appliance_type,
        serial_number=device.serial_number,
    )


class BradfordWhiteWaveBaseEntity[CoordinatorT: DataUpdateCoordinator](
    CoordinatorEntity[CoordinatorT]
):
    """Base entity for Bradford White Wave."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CoordinatorT, mac_address: str, info: DeviceInfo) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.mac_address = mac_address
        self._device_info = info

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return self._device_info


class BradfordWhiteWaveStatusEntity(
    BradfordWhiteWaveBaseEntity[BradfordWhiteWaveStatusCoordinator]
):
    """Base entity for status-backed platforms (water heater, select)."""

    def __init__(
        self,
        coordinator: BradfordWhiteWaveStatusCoordinator,
        mac_address: str,
        info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator, mac_address, info)

    @property
    def device(self) -> DeviceStatus | None:
        """Get the device from the coordinator data."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.mac_address)


class BradfordWhiteWaveEnergyEntity(
    BradfordWhiteWaveBaseEntity[BradfordWhiteWaveEnergyCoordinator]
):
    """Base entity for energy sensors."""

    def __init__(
        self,
        coordinator: BradfordWhiteWaveEnergyCoordinator,
        mac_address: str,
        info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator, mac_address, info)

    @property
    def device_data(self) -> dict[str, list[EnergyUsage]] | None:
        """Get the device data from the coordinator."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.mac_address)
