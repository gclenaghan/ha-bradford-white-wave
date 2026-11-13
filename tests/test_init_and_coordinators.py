"""Tests for entry lifecycle and data update coordinators."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bradford_white_wave_client import (
    BradfordWhiteAuthError,
    BradfordWhiteConnectError,
    DeviceStatus,
    EnergyUsage,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from custom_components.bradford_white_wave import (
    PLATFORMS,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.bradford_white_wave.const import FAST_INTERVAL, REGULAR_INTERVAL
from custom_components.bradford_white_wave.coordinator import (
    BradfordWhiteWaveEnergyCoordinator,
    BradfordWhiteWaveStatusCoordinator,
)

from .conftest import FAKE_HA_SESSION


async def test_setup_entry_populates_runtime_data_and_persists_rotated_tokens(
    sample_summary_device: DeviceStatus,
    sample_detailed_device: DeviceStatus,
    sample_energy_point: EnergyUsage,
) -> None:
    """Verify runtime_data setup, platform forwarding, token callback, and unload."""
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    entry = ConfigEntry(
        entry_id="entry-1",
        data={"email": "u@example.com", "password": "pw", "refresh_token": "rt-old"},
    )

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.list_devices = AsyncMock(return_value=[sample_summary_device])
    mock_client.get_status = AsyncMock(return_value=sample_detailed_device)
    mock_client.get_energy_usage = AsyncMock(return_value=[sample_energy_point])
    mock_client.close = AsyncMock()

    with patch(
        "custom_components.bradford_white_wave.BradfordWhiteClient",
        return_value=mock_client,
    ) as client_cls:
        ok = await async_setup_entry(hass, entry)

    assert ok is True
    assert PLATFORMS == [Platform.SELECT, Platform.SENSOR, Platform.WATER_HEATER]
    assert entry.runtime_data is not None
    assert entry.runtime_data.client is mock_client

    # Energy coordinator reused status_coordinator.data instead of calling list_devices twice!
    mock_client.list_devices.assert_awaited_once()

    # Merged metadata preserved appliance_type from summary onto detailed status!
    merged_device = entry.runtime_data.status_coordinator.data["AA:BB:CC:DD:EE:FF"]
    assert merged_device.appliance_type == "AeroTherm G2"
    assert merged_device.access_level == 1
    assert merged_device.setpoint_fahrenheit == 120

    # Verify session injection and refresh token persistence callback
    kwargs = client_cls.call_args.kwargs
    assert kwargs["session"] is FAKE_HA_SESSION
    on_token_update = kwargs["on_token_update"]

    # Unchanged token does not write to config entry
    on_token_update("rt-old")
    hass.config_entries.async_update_entry.assert_not_called()

    # Rotated token updates entry.data
    on_token_update("rt-new")
    hass.config_entries.async_update_entry.assert_called_once_with(
        entry,
        data={"email": "u@example.com", "password": "pw", "refresh_token": "rt-new"},
    )

    unloaded = await async_unload_entry(hass, entry)
    assert unloaded is True
    mock_client.close.assert_awaited_once()


@pytest.mark.parametrize(
    ("raised_exc", "expected_ha_exc"),
    [
        (BradfordWhiteAuthError("revoked"), ConfigEntryAuthFailed),
        (BradfordWhiteConnectError("offline"), ConfigEntryNotReady),
        (RuntimeError("unexpected"), ConfigEntryNotReady),
    ],
)
async def test_setup_entry_auth_and_connect_errors_close_client(
    raised_exc: Exception, expected_ha_exc: type[Exception]
) -> None:
    """Verify setup failures map to HA exceptions and close the client."""
    hass = MagicMock()
    entry = ConfigEntry(data={"refresh_token": "rt"})

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock(side_effect=raised_exc)
    mock_client.close = AsyncMock()

    with (
        patch(
            "custom_components.bradford_white_wave.BradfordWhiteClient",
            return_value=mock_client,
        ),
        pytest.raises(expected_ha_exc),
    ):
        await async_setup_entry(hass, entry)

    mock_client.close.assert_awaited_once()


async def test_status_coordinator_skips_list_devices_during_fast_polling(
    sample_summary_device: DeviceStatus,
    sample_detailed_device: DeviceStatus,
) -> None:
    """Verify fast polling reuses cached devices and reverts after 60s monotonic window."""
    hass = MagicMock()
    entry = ConfigEntry()
    client = MagicMock()
    client.list_devices = AsyncMock(return_value=[sample_summary_device])
    client.get_status = AsyncMock(return_value=sample_detailed_device)

    coord = BradfordWhiteWaveStatusCoordinator(hass, client, entry)

    with patch(
        "custom_components.bradford_white_wave.coordinator.time.monotonic",
        side_effect=[100.0, 110.0, 165.0],
    ):
        await coord.async_config_entry_first_refresh()
        assert client.list_devices.await_count == 1
        assert coord.update_interval == REGULAR_INTERVAL

        # Trigger optimistic write at t=100.0 -> sets FAST_INTERVAL and updates state immediately
        coord.apply_optimistic_temperature("AA:BB:CC:DD:EE:FF", 130)
        assert coord.update_interval == FAST_INTERVAL
        assert coord.data["AA:BB:CC:DD:EE:FF"].setpoint_fahrenheit == 130

        # Fast poll at t=110.0 (10s elapsed < 60s): skips list_devices()!
        await coord.async_request_refresh()
        assert client.list_devices.await_count == 1
        assert client.get_status.await_count == 2
        assert coord.update_interval == FAST_INTERVAL

        # Poll at t=165.0 (65s elapsed >= 60s): reverts to REGULAR_INTERVAL and calls list_devices()
        await coord.async_request_refresh()
        assert coord.update_interval == REGULAR_INTERVAL
        assert client.list_devices.await_count == 2


async def test_energy_coordinator_falls_back_to_list_devices_when_status_empty(
    sample_summary_device: DeviceStatus,
    sample_energy_point: EnergyUsage,
) -> None:
    """Verify energy coordinator calls list_devices only if status coordinator has no data."""
    hass = MagicMock()
    entry = ConfigEntry()
    client = MagicMock()
    client.list_devices = AsyncMock(return_value=[sample_summary_device])
    client.get_energy_usage = AsyncMock(return_value=[sample_energy_point])

    energy_coord = BradfordWhiteWaveEnergyCoordinator(hass, client, entry, None)
    await energy_coord.async_config_entry_first_refresh()

    client.list_devices.assert_awaited_once()
    assert set(energy_coord.data["AA:BB:CC:DD:EE:FF"].keys()) == {"weekly", "monthly"}
