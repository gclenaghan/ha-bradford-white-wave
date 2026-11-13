"""The Bradford White Wave integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from bradford_white_wave_client import (
    BradfordWhiteAuthError,
    BradfordWhiteClient,
    BradfordWhiteConnectError,
)

from .const import CONF_REFRESH_TOKEN, DOMAIN
from .coordinator import (
    BradfordWhiteWaveEnergyCoordinator,
    BradfordWhiteWaveStatusCoordinator,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SELECT, Platform.SENSOR, Platform.WATER_HEATER]


@dataclass
class BradfordWhiteWaveData:
    """Data for the Bradford White Wave integration."""

    client: BradfordWhiteClient
    status_coordinator: BradfordWhiteWaveStatusCoordinator
    energy_coordinator: BradfordWhiteWaveEnergyCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bradford White Wave from a config entry."""
    refresh_token = entry.data.get(CONF_REFRESH_TOKEN)
    email = entry.data.get(CONF_EMAIL)
    password = entry.data.get(CONF_PASSWORD)

    @callback
    def _async_persist_refresh_token(new_refresh_token: str) -> None:
        """Persist rotated refresh tokens to the config entry."""
        if entry.data.get(CONF_REFRESH_TOKEN) != new_refresh_token:
            _LOGGER.debug("Persisting updated refresh token to config entry")
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, CONF_REFRESH_TOKEN: new_refresh_token},
            )

    client = BradfordWhiteClient(
        refresh_token=refresh_token,
        email=email,
        password=password,
        session=async_get_clientsession(hass),
        on_token_update=_async_persist_refresh_token,
    )
    try:
        await client.authenticate()
    except BradfordWhiteAuthError as ex:
        await client.close()
        raise ConfigEntryAuthFailed(f"Authentication failed with Bradford White Wave: {ex}") from ex
    except BradfordWhiteConnectError as ex:
        await client.close()
        raise ConfigEntryNotReady(f"Failed to connect to Bradford White Wave: {ex}") from ex
    except Exception as ex:
        await client.close()
        _LOGGER.exception("Unexpected error authenticating with Bradford White Wave")
        raise ConfigEntryNotReady(
            f"Unexpected error connecting to Bradford White Wave: {ex}"
        ) from ex

    status_coordinator = BradfordWhiteWaveStatusCoordinator(hass, client, entry)
    await status_coordinator.async_config_entry_first_refresh()

    energy_coordinator = BradfordWhiteWaveEnergyCoordinator(hass, client, entry, status_coordinator)
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
