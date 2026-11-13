"""The data update coordinators for the Bradford White Wave integration."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from bradford_white_wave_client import (
    BradfordWhiteAuthError,
    BradfordWhiteClient,
    BradfordWhiteConnectError,
    BradfordWhiteMode,
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
            config_entry=entry,
            name=f"{DOMAIN}_status",
            update_interval=REGULAR_INTERVAL,
        )
        self.client = client
        self.entry = entry
        self._last_control_monotonic: float | None = None
        self._devices_cache: list[DeviceStatus] = []

    def _is_fast_poll_active(self) -> bool:
        """Return True if within the fast-polling window following a control action."""
        if self._last_control_monotonic is None:
            return False
        return (time.monotonic() - self._last_control_monotonic) < REGULAR_INTERVAL.total_seconds()

    @callback
    def mark_control_action(self) -> None:
        """Record a control write and switch to the fast polling interval."""
        self._last_control_monotonic = time.monotonic()
        if self.update_interval != FAST_INTERVAL:
            _LOGGER.debug("Setting fast update interval")
            self.update_interval = FAST_INTERVAL

    @callback
    def apply_optimistic_temperature(self, mac_address: str, temperature: int) -> None:
        """Update cached device setpoint optimistically and schedule fast polling."""
        self.mark_control_action()
        if self.data and (current := self.data.get(mac_address)) is not None:
            updated = current.model_copy(update={"setpoint_fahrenheit": temperature})
            self.async_set_updated_data({**self.data, mac_address: updated})

    @callback
    def apply_optimistic_mode(self, mac_address: str, mode: BradfordWhiteMode) -> None:
        """Update cached device mode optimistically and schedule fast polling."""
        self.mark_control_action()
        if self.data and (current := self.data.get(mac_address)) is not None:
            updated = current.model_copy(update={"heat_mode_value": int(mode)})
            self.async_set_updated_data({**self.data, mac_address: updated})

    async def _async_update_data(self) -> dict[str, DeviceStatus]:
        """Fetch latest data from the device status endpoint."""
        try:
            fast_poll = self._is_fast_poll_active()
            if fast_poll:
                if self.update_interval != FAST_INTERVAL:
                    _LOGGER.debug("Setting fast update interval")
                    self.update_interval = FAST_INTERVAL
            elif (
                self._last_control_monotonic is not None or self.update_interval != REGULAR_INTERVAL
            ):
                _LOGGER.debug("Setting regular update interval")
                self.update_interval = REGULAR_INTERVAL
                self._last_control_monotonic = None

            if fast_poll and self._devices_cache:
                devices = self._devices_cache
            else:
                devices = await self.client.list_devices()
                self._devices_cache = devices

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
        status_coordinator: BradfordWhiteWaveStatusCoordinator | None = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_energy",
            update_interval=ENERGY_USAGE_INTERVAL,
        )
        self.client = client
        self.entry = entry
        self.status_coordinator = status_coordinator

    async def _async_update_data(self) -> dict[str, dict[str, list[EnergyUsage]]]:
        """Fetch latest energy data."""
        data: dict[str, dict[str, list[EnergyUsage]]] = {}

        try:
            if self.status_coordinator and self.status_coordinator.data:
                devices = list(self.status_coordinator.data.values())
            else:
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


@dataclass
class BradfordWhiteWaveData:
    """Runtime data for the Bradford White Wave integration."""

    client: BradfordWhiteClient
    status_coordinator: BradfordWhiteWaveStatusCoordinator
    energy_coordinator: BradfordWhiteWaveEnergyCoordinator


type BradfordWhiteConfigEntry = ConfigEntry[BradfordWhiteWaveData]
