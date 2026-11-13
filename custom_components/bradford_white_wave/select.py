"""Select platform for Bradford White Wave operation modes."""

from __future__ import annotations

from bradford_white_wave_client import (
    BradfordWhiteAuthError,
    BradfordWhiteConnectError,
    BradfordWhiteMode,
)
from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BW_TO_SELECT_OPTIONS, SELECT_OPTIONS_TO_BW
from .coordinator import BradfordWhiteConfigEntry, BradfordWhiteWaveStatusCoordinator
from .entity import BradfordWhiteWaveStatusEntity, build_device_info

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BradfordWhiteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Bradford White Wave select platform."""
    coordinator = entry.runtime_data.status_coordinator

    entities = [
        BradfordWhiteWaveModeSelect(coordinator, mac, build_device_info(mac, device))
        for mac, device in coordinator.data.items()
    ]

    async_add_entities(entities)


class BradfordWhiteWaveModeSelect(BradfordWhiteWaveStatusEntity, SelectEntity):
    """Select entity exposing native Bradford White Wave operation modes."""

    _attr_translation_key = "operation_mode"

    def __init__(
        self,
        coordinator: BradfordWhiteWaveStatusCoordinator,
        mac_address: str,
        info: DeviceInfo,
    ) -> None:
        """Initialize the operation mode select entity."""
        super().__init__(coordinator, mac_address, info)
        self._attr_unique_id = f"{mac_address}_operation_mode"
        self._attr_options = list(SELECT_OPTIONS_TO_BW.keys())

    @property
    def current_option(self) -> str | None:
        """Return the active Bradford White operation mode option."""
        if not self.device or self.device.heating_mode is None:
            return None
        return BW_TO_SELECT_OPTIONS.get(self.device.heating_mode)

    async def async_select_option(self, option: str) -> None:
        """Change the Bradford White operation mode."""
        bw_mode = SELECT_OPTIONS_TO_BW.get(option)
        if bw_mode is None:
            raise ServiceValidationError(f"Unsupported Bradford White operation mode: {option}")

        try:
            response = await self.coordinator.client.set_mode(self.mac_address, bw_mode)
        except BradfordWhiteAuthError as err:
            self.coordinator.entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                f"Authentication failed while changing operation mode: {err}"
            ) from err
        except BradfordWhiteConnectError as err:
            raise HomeAssistantError(
                f"Failed to communicate with Bradford White Wave: {err}"
            ) from err

        applied_mode = bw_mode
        if response.actual_mode is not None:
            try:
                applied_mode = BradfordWhiteMode(response.actual_mode)
            except ValueError:
                applied_mode = bw_mode

        self.coordinator.apply_optimistic_mode(self.mac_address, applied_mode)
