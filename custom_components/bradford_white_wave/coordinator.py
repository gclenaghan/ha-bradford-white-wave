"""The data update coordinator for the Bradford White Wave integration."""

import datetime
import logging
from typing import Dict, Any

from bradford_white_wave_client import (
    BradfordWhiteClient,
    BradfordWhiteConnectError,
)
from bradford_white_wave_client.models import DeviceStatus, EnergyUsage

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    REGULAR_INTERVAL,
    FAST_INTERVAL,
    ENERGY_USAGE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class BradfordWhiteWaveStatusCoordinator(DataUpdateCoordinator[Dict[str, DeviceStatus]]):
    """Coordinator for device status, updating with a frequent interval."""

    def __init__(self, hass: HomeAssistant, client: BradfordWhiteClient) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_status", update_interval=REGULAR_INTERVAL)
        self.client = client
        self.shared_data: Dict[str, Any] = {}

    async def _async_update_data(self) -> Dict[str, DeviceStatus]:
        """Fetch latest data from the device status endpoint."""
        try:
            # Check if we should use fast interval
            last_api_set = self.shared_data.get("last_api_set_datetime")
            if last_api_set:
                if (datetime.datetime.now() - last_api_set) < REGULAR_INTERVAL:
                    if self.update_interval != FAST_INTERVAL:
                        _LOGGER.debug("Setting fast update interval")
                        self.update_interval = FAST_INTERVAL
                else:
                    if self.update_interval != REGULAR_INTERVAL:
                        _LOGGER.debug("Setting regular update interval")
                        self.update_interval = REGULAR_INTERVAL
                        self.shared_data["last_api_set_datetime"] = None

            devices = await self.client.list_devices()
            
            device_map = {}
            for device in devices:
                detailed_device = await self.client.get_status(device.mac_address)
                device_map[detailed_device.mac_address] = detailed_device

            return device_map
            
        except BradfordWhiteConnectError as err:
            # We can try to differentiate auth errors if possible, 
            # but generic error handling is safer for now.
             if "401" in str(err) or "Access denied" in str(err):
                raise ConfigEntryAuthFailed from err
             raise UpdateFailed(f"Error communicating with API: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err


class BradfordWhiteWaveEnergyCoordinator(DataUpdateCoordinator[Dict[str, Dict[str, list[EnergyUsage]]]]):
    """Coordinator for energy usage data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: BradfordWhiteClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass, _LOGGER, name=f"{DOMAIN}_energy", update_interval=ENERGY_USAGE_INTERVAL
        )
        self.client = client

    async def _async_update_data(self) -> Dict[str, Dict[str, list[EnergyUsage]]]:
        """Fetch latest energy data."""
        # Structure: data[mac][view_type] = List[EnergyUsage]
        data: Dict[str, Dict[str, list[EnergyUsage]]] = {}
        
        try:
            devices = await self.client.list_devices()
            
            for device in devices:
                device_data = {}
                # We want 4 views: hourly, daily, weekly, monthly
                for view_type in ["hourly", "daily", "weekly", "monthly"]:
                    usage = await self.client.get_energy_usage(device.mac_address, view_type)
                    device_data[view_type] = usage
                
                data[device.mac_address] = device_data
                
        except BradfordWhiteConnectError as err:
            if "401" in str(err):
                raise ConfigEntryAuthFailed from err
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except Exception as err:
             raise UpdateFailed(f"Unexpected error: {err}") from err

        return data
