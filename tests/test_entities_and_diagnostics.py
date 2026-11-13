"""Tests for entities, diagnostics redaction, and manifest/translation files."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from bradford_white_wave_client import (
    BradfordWhiteAuthError,
    BradfordWhiteConnectError,
    DeviceStatus,
    EnergyUsage,
    WriteResponse,
)
from homeassistant.components.sensor import RestoredSensorData
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.bradford_white_wave.coordinator import (
    BradfordWhiteWaveData,
    BradfordWhiteWaveEnergyCoordinator,
    BradfordWhiteWaveStatusCoordinator,
)
from custom_components.bradford_white_wave.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.bradford_white_wave.entity import build_device_info
from custom_components.bradford_white_wave.select import (
    PARALLEL_UPDATES as SELECT_PARALLEL_UPDATES,
)
from custom_components.bradford_white_wave.select import (
    BradfordWhiteWaveModeSelect,
)
from custom_components.bradford_white_wave.select import (
    async_setup_entry as async_setup_select_entry,
)
from custom_components.bradford_white_wave.sensor import (
    PARALLEL_UPDATES as SENSOR_PARALLEL_UPDATES,
)
from custom_components.bradford_white_wave.sensor import (
    BradfordWhiteWaveEnergySensor,
)
from custom_components.bradford_white_wave.sensor import (
    async_setup_entry as async_setup_sensor_entry,
)
from custom_components.bradford_white_wave.water_heater import (
    PARALLEL_UPDATES as WH_PARALLEL_UPDATES,
)
from custom_components.bradford_white_wave.water_heater import (
    BradfordWhiteWaveWaterHeater,
)
from custom_components.bradford_white_wave.water_heater import (
    async_setup_entry as async_setup_water_heater_entry,
)

from .conftest import REDACTED

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPONENT_DIR = REPO_ROOT / "custom_components" / "bradford_white_wave"


def test_manifest_hacs_translations_and_icons_sync() -> None:
    """Validate manifest.json, hacs.json, strings.json, en.json, and icons.json."""
    manifest = json.loads((COMPONENT_DIR / "manifest.json").read_text())
    assert manifest["domain"] == "bradford_white_wave"
    assert manifest["version"] == "1.1.0b2"
    assert manifest["requirements"] == ["bradford-white-wave-client>=1.0.0"]
    keys = list(manifest.keys())
    assert keys[:2] == ["domain", "name"]
    assert keys[2:] == sorted(keys[2:])

    hacs = json.loads((REPO_ROOT / "hacs.json").read_text())
    assert hacs["homeassistant"] == "2026.11.0"

    strings = json.loads((COMPONENT_DIR / "strings.json").read_text())
    en = json.loads((COMPONENT_DIR / "translations" / "en.json").read_text())
    assert strings == en

    icons = json.loads((COMPONENT_DIR / "icons.json").read_text())
    assert set(icons["entity"].keys()) == set(strings["entity"].keys())
    for platform_key, platform_strings in strings["entity"].items():
        assert set(icons["entity"][platform_key].keys()) == set(platform_strings.keys())
        for entity_key, icon_spec in icons["entity"][platform_key].items():
            assert icon_spec["default"].startswith("mdi:")
            if "state" in platform_strings[entity_key]:
                assert set(icon_spec["state"].keys()) == set(
                    platform_strings[entity_key]["state"].keys()
                )


def test_parallel_updates_constants() -> None:
    """Ensure action platforms serialize writes while read-only sensors do not."""
    assert WH_PARALLEL_UPDATES == 1
    assert SELECT_PARALLEL_UPDATES == 1
    assert SENSOR_PARALLEL_UPDATES == 0


async def test_water_heater_and_select_entities_stay_synchronized(
    sample_summary_device: DeviceStatus,
    sample_detailed_device: DeviceStatus,
) -> None:
    """Test native 2026.11 properties, bounds validation, away-mode memory, and select sync."""
    hass = MagicMock()
    entry = ConfigEntry()
    client = MagicMock()
    client.list_devices = AsyncMock(return_value=[sample_summary_device])
    client.get_status = AsyncMock(return_value=sample_detailed_device)
    client.set_temperature = AsyncMock(
        return_value=WriteResponse(status="ok", actual_temperature=128)
    )
    client.set_mode = AsyncMock(
        side_effect=lambda _mac, mode: WriteResponse(status="ok", actual_mode=int(mode))
    )

    status_coord = BradfordWhiteWaveStatusCoordinator(hass, client, entry)
    await status_coord.async_config_entry_first_refresh()

    mac = "AA:BB:CC:DD:EE:FF"
    info = build_device_info(mac, status_coord.data[mac])
    assert info["model"] == "AeroTherm G2"

    wh = BradfordWhiteWaveWaterHeater(status_coord, mac, info)
    mode_select = BradfordWhiteWaveModeSelect(status_coord, mac, info)
    await wh.async_added_to_hass()
    await mode_select.async_added_to_hass()

    # Verify legacy HA <2026.11 attributes are not defined on BradfordWhiteWaveWaterHeater
    assert not hasattr(BradfordWhiteWaveWaterHeater, "_attr_temperature_unit")
    assert "target_temperature" not in BradfordWhiteWaveWaterHeater.__dict__
    assert wh.native_target_temperature == 120.0
    assert wh.current_operation == "eco"  # HYBRID
    assert wh.is_away_mode_on is False
    assert mode_select.current_option == "hybrid"

    # Bounds validation rejects out-of-range temperatures before calling API
    with pytest.raises(ServiceValidationError):
        await wh.async_set_temperature(temperature=95)
    with pytest.raises(ServiceValidationError):
        await wh.async_set_temperature(temperature=145)
    client.set_temperature.assert_not_awaited()

    # Valid temperature applies WriteResponse.actual_temperature optimistically
    await wh.async_set_temperature(temperature=127.6)
    client.set_temperature.assert_awaited_once_with(mac, 128)
    assert wh.native_target_temperature == 128.0

    # Changing mode via SelectEntity updates both SelectEntity and WaterHeaterEntity + away memory!
    await mode_select.async_select_option("hybrid_plus")
    assert mode_select.current_option == "hybrid_plus"
    assert wh.current_operation == "high_demand"

    # Turning away mode on switches to VACATION; turning away mode off restores HYBRID_PLUS!
    await wh.async_turn_away_mode_on()
    assert wh.is_away_mode_on is True
    assert mode_select.current_option == "vacation"

    await wh.async_turn_away_mode_off()
    assert wh.is_away_mode_on is False
    assert wh.current_operation == "high_demand"
    assert mode_select.current_option == "hybrid_plus"

    # Invalid mode options raise ServiceValidationError
    with pytest.raises(ServiceValidationError):
        await wh.async_set_operation_mode("invalid")
    with pytest.raises(ServiceValidationError):
        await mode_select.async_select_option("invalid")

    # Auth and connect errors wrap into HomeAssistantError (triggering reauth on auth error)
    client.set_mode = AsyncMock(side_effect=BradfordWhiteAuthError("expired"))
    with pytest.raises(HomeAssistantError):
        await mode_select.async_select_option("heat_pump")
    entry.async_start_reauth.assert_called_once_with(hass)

    client.set_mode = AsyncMock(side_effect=BradfordWhiteConnectError("timeout"))
    with pytest.raises(HomeAssistantError):
        await wh.async_set_operation_mode("heat_pump")


async def test_energy_sensor_restores_state_and_filters_jitter(
    sample_energy_point: EnergyUsage,
) -> None:
    """Verify RestoreSensor seeds jitter filter across restarts and handles resets."""
    hass = MagicMock()
    entry = ConfigEntry()
    client = MagicMock()
    energy_coord = BradfordWhiteWaveEnergyCoordinator(hass, client, entry)

    mac = "AA:BB:CC:DD:EE:FF"
    # Simulate slightly lower initial reading right after HA restart (12.41 vs prior 12.45)
    energy_coord.data = {
        mac: {
            "weekly": [sample_energy_point.model_copy(update={"total_energy": 12.41})],
            "monthly": [sample_energy_point],
        }
    }

    sensor = BradfordWhiteWaveEnergySensor(
        energy_coord, mac, {"name": "Home"}, "weekly", "total_energy"
    )
    sensor._restored_sensor_data = RestoredSensorData(native_value="12.45")

    await sensor.async_added_to_hass()
    # Jitter dip from 12.45 -> 12.41 on startup is filtered out!
    assert sensor.native_value == 12.45

    # Normal upward progression updates value
    energy_coord.async_set_updated_data(
        {
            mac: {
                "weekly": [sample_energy_point.model_copy(update={"total_energy": 12.80})],
                "monthly": [sample_energy_point],
            }
        }
    )
    assert sensor.native_value == 12.80

    # Significant drop (weekly period rollover) updates value
    energy_coord.async_set_updated_data(
        {
            mac: {
                "weekly": [sample_energy_point.model_copy(update={"total_energy": 0.04})],
                "monthly": [sample_energy_point],
            }
        }
    )
    assert sensor.native_value == 0.04


async def test_diagnostics_redacts_credentials_and_identifiers(
    sample_summary_device: DeviceStatus,
    sample_detailed_device: DeviceStatus,
    sample_energy_point: EnergyUsage,
) -> None:
    """Verify diagnostics redacts credentials, tokens, MACs, serials, and request IDs."""
    hass = MagicMock()
    entry = ConfigEntry(
        entry_id="entry-diag",
        data={
            "email": "secret@example.com",
            "password": "super-secret-password",
            "refresh_token": "secret-refresh-token",
        },
    )
    client = MagicMock()
    client.access_token = "secret-access-token"
    client.refresh_token = "secret-refresh-token"
    client.list_devices = AsyncMock(return_value=[sample_summary_device])
    client.get_status = AsyncMock(return_value=sample_detailed_device)
    client.get_energy_usage = AsyncMock(return_value=[sample_energy_point])

    status_coord = BradfordWhiteWaveStatusCoordinator(hass, client, entry)
    await status_coord.async_config_entry_first_refresh()
    energy_coord = BradfordWhiteWaveEnergyCoordinator(hass, client, entry, status_coord)
    await energy_coord.async_config_entry_first_refresh()

    entry.runtime_data = BradfordWhiteWaveData(client, status_coord, energy_coord)

    diag = await async_get_config_entry_diagnostics(hass, entry)
    serialized = json.dumps(diag)

    # Sensitive values must never appear anywhere in the serialized JSON
    for sensitive in (
        "secret@example.com",
        "super-secret-password",
        "secret-refresh-token",
        "secret-access-token",
        "AA:BB:CC:DD:EE:FF",
        "BJ55834840",
        "req-999",
    ):
        assert sensitive not in serialized

    assert diag["entry"]["data"]["email"] == REDACTED
    assert diag["entry"]["data"]["password"] == REDACTED
    assert diag["entry"]["data"]["refresh_token"] == REDACTED
    device_diag = diag["status_coordinator"]["devices"]["device_1"]
    assert device_diag["mac_address"] == REDACTED
    assert device_diag["serial_number"] == REDACTED
    assert device_diag["request_id"] == REDACTED
    assert device_diag["appliance_type"] == "AeroTherm G2"
    assert device_diag["setpoint_fahrenheit"] == 120


async def test_platform_setup_entrypoints_register_expected_entities(
    sample_summary_device: DeviceStatus,
    sample_detailed_device: DeviceStatus,
    sample_energy_point: EnergyUsage,
) -> None:
    """Verify water_heater, select, and sensor async_setup_entry wire runtime_data."""
    hass = MagicMock()
    entry = ConfigEntry()
    client = MagicMock()
    client.list_devices = AsyncMock(return_value=[sample_summary_device])
    client.get_status = AsyncMock(return_value=sample_detailed_device)
    client.get_energy_usage = AsyncMock(return_value=[sample_energy_point])

    status_coord = BradfordWhiteWaveStatusCoordinator(hass, client, entry)
    await status_coord.async_config_entry_first_refresh()
    energy_coord = BradfordWhiteWaveEnergyCoordinator(hass, client, entry, status_coord)
    await energy_coord.async_config_entry_first_refresh()
    entry.runtime_data = BradfordWhiteWaveData(client, status_coord, energy_coord)

    added_wh: list[BradfordWhiteWaveWaterHeater] = []
    added_select: list[BradfordWhiteWaveModeSelect] = []
    added_sensors: list[BradfordWhiteWaveEnergySensor] = []

    await async_setup_water_heater_entry(hass, entry, added_wh.extend)
    await async_setup_select_entry(hass, entry, added_select.extend)
    await async_setup_sensor_entry(hass, entry, added_sensors.extend)

    assert len(added_wh) == 1
    assert len(added_select) == 1
    assert len(added_sensors) == 6
    assert added_wh[0].device_info["model"] == "AeroTherm G2"
    assert added_select[0].device_info["model"] == "AeroTherm G2"
    assert added_sensors[0].device_info["model"] == "AeroTherm G2"
