"""The Bradford White Wave integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from bradford_white_wave_client import BradfordWhiteClient
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from .const import DOMAIN
from .coordinator import (
    BradfordWhiteWaveStatusCoordinator,
    BradfordWhiteWaveEnergyCoordinator,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.WATER_HEATER]


@dataclass
class BradfordWhiteWaveData:
    """Data for the Bradford White Wave integration."""

    client: BradfordWhiteClient
    status_coordinator: BradfordWhiteWaveStatusCoordinator
    energy_coordinator: BradfordWhiteWaveEnergyCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bradford White Wave from a config entry."""

    refresh_token = entry.data["refresh_token"]

    client = BradfordWhiteClient(refresh_token)
    try:
        await client.authenticate()
        # Persist token if changed during initial auth
        if client.refresh_token and client.refresh_token != entry.data.get(
            "refresh_token"
        ):
            _LOGGER.info("Refresh token updated during init, saving to config entry.")
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, "refresh_token": client.refresh_token}
            )
    except Exception as ex:
        _LOGGER.error("Failed to authenticate with Bradford White Wave: %s", ex)
        raise

    status_coordinator = BradfordWhiteWaveStatusCoordinator(hass, client, entry)
    energy_coordinator = BradfordWhiteWaveEnergyCoordinator(hass, client, entry)

    await status_coordinator.async_config_entry_first_refresh()
    await energy_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = BradfordWhiteWaveData(
        client, status_coordinator, energy_coordinator
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data: BradfordWhiteWaveData = hass.data[DOMAIN].pop(entry.entry_id)
        await data.client.close()

    return unload_ok
