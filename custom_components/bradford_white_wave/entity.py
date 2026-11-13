"""Base entity for Bradford White Wave."""

from __future__ import annotations

from typing import Generic, TypeVar

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from bradford_white_wave_client import DeviceStatus, EnergyUsage

from .coordinator import (
    BradfordWhiteWaveEnergyCoordinator,
    BradfordWhiteWaveStatusCoordinator,
)

_CoordinatorT = TypeVar("_CoordinatorT", bound=DataUpdateCoordinator)


class BradfordWhiteWaveBaseEntity(CoordinatorEntity[_CoordinatorT], Generic[_CoordinatorT]):
    """Base entity for Bradford White Wave."""

    def __init__(self, coordinator: _CoordinatorT, mac_address: str, info: DeviceInfo) -> None:
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
    """Base entity for status (water heater)."""

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
