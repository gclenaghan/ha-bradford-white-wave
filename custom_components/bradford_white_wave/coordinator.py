"""The data update coordinators for the Bradford White Wave integration."""

from __future__ import annotations

import datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from bradford_white_wave_client import (
    BradfordWhiteAuthError,
    BradfordWhiteClient,
    BradfordWhiteConnectError,
    DeviceStatus,
    EnergyUsage,
    EnergyViewType,
)

from .const import (
    DOMAIN,
    ENERGY_USAGE_INTERVAL,
    FAST_INTERVAL,
    REGULAR_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

ENABLED_ENERGY_VIEWS: tuple[EnergyViewType, ...] = (
    EnergyViewType.WEEKLY,
    EnergyViewType.MONTHLY,
)


def _merge_device_metadata(summary: DeviceStatus, detailed: DeviceStatus) -> DeviceStatus:
    """Preserve list-only metadata (such as appliance_type) on detailed status objects."""
    return detailed.model_copy(
        update={
            "friendly_name": detailed.friendly_name or summary.friendly_name,
            "serial_number": detailed.serial_number or summary.serial_number,
            "appliance_type": detailed.appliance_type or summary.appliance_type,
            "access_level": (
                detailed.access_level if detailed.access_level is not None else summary.access_level
            ),
        }
    )


class BradfordWhiteWaveStatusCoordinator(DataUpdateCoordinator[dict[str, DeviceStatus]]):
    """Coordinator for device status, updating with a frequent interval."""

    def __init__(
        self, hass: HomeAssistant, client: BradfordWhiteClient, entry: ConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_status",
            update_interval=REGULAR_INTERVAL,
        )
        self.client = client
        self.entry = entry
        self.shared_data: dict[str, Any] = {}

    async def _async_update_data(self) -> dict[str, DeviceStatus]:
        """Fetch latest data from the device status endpoint."""
        try:
            last_api_set = self.shared_data.get("last_api_set_datetime")
            if last_api_set:
                if (datetime.datetime.now() - last_api_set) < REGULAR_INTERVAL:
                    if self.update_interval != FAST_INTERVAL:
                        _LOGGER.debug("Setting fast update interval")
                        self.update_interval = FAST_INTERVAL
                elif self.update_interval != REGULAR_INTERVAL:
                    _LOGGER.debug("Setting regular update interval")
                    self.update_interval = REGULAR_INTERVAL
                    self.shared_data["last_api_set_datetime"] = None

            devices = await self.client.list_devices()

            device_map: dict[str, DeviceStatus] = {}
            for device in devices:
                detailed_device = await self.client.get_status(device.mac_address)
                merged = _merge_device_metadata(device, detailed_device)
                device_map[merged.mac_address] = merged

            return device_map

        except BradfordWhiteAuthError as err:
            raise ConfigEntryAuthFailed(
                f"Authentication failed while updating status: {err}"
            ) from err
        except BradfordWhiteConnectError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err


class BradfordWhiteWaveEnergyCoordinator(
    DataUpdateCoordinator[dict[str, dict[str, list[EnergyUsage]]]]
):
    """Coordinator for energy usage data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: BradfordWhiteClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_energy",
            update_interval=ENERGY_USAGE_INTERVAL,
        )
        self.client = client
        self.entry = entry

    async def _async_update_data(self) -> dict[str, dict[str, list[EnergyUsage]]]:
        """Fetch latest energy data."""
        data: dict[str, dict[str, list[EnergyUsage]]] = {}

        try:
            devices = await self.client.list_devices()

            for device in devices:
                device_data: dict[str, list[EnergyUsage]] = {}
                for view_type in ENABLED_ENERGY_VIEWS:
                    usage = await self.client.get_energy_usage(device.mac_address, view_type)
                    device_data[view_type.value] = usage

                data[device.mac_address] = device_data

        except BradfordWhiteAuthError as err:
            raise ConfigEntryAuthFailed(
                f"Authentication failed while updating energy usage: {err}"
            ) from err
        except BradfordWhiteConnectError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err

        return data
