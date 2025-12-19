"""Base entity for Bradford White Wave."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BradfordWhiteWaveStatusCoordinator, BradfordWhiteWaveEnergyCoordinator

class BradfordWhiteWaveBaseEntity(CoordinatorEntity):
    """Base entity."""

    def __init__(self, coordinator, mac_address: str, info: DeviceInfo):
        """Initialize the entity."""
        super().__init__(coordinator)
        self.mac_address = mac_address
        self._device_info = info

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return self._device_info


class BradfordWhiteWaveStatusEntity(BradfordWhiteWaveBaseEntity):
    """Base entity for status (water heater)."""
    
    def __init__(self, coordinator: BradfordWhiteWaveStatusCoordinator, mac_address: str, info: DeviceInfo):
        super().__init__(coordinator, mac_address, info)
        
    @property
    def device(self):
        """Get the device from the coordinator data."""
        return self.coordinator.data.get(self.mac_address)


class BradfordWhiteWaveEnergyEntity(BradfordWhiteWaveBaseEntity):
    """Base entity for energy sensors."""

    def __init__(self, coordinator: BradfordWhiteWaveEnergyCoordinator, mac_address: str, info: DeviceInfo):
        super().__init__(coordinator, mac_address, info)

    @property
    def device_data(self):
        """Get the device data from the coordinator."""
        # data structure: data[mac][view_type] = List[EnergyUsage]
        return self.coordinator.data.get(self.mac_address)
