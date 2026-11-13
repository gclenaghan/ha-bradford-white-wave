"""Test fixtures and lightweight Home Assistant stubs for unit testing."""

from __future__ import annotations

import importlib.util
import sys
import types
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
import voluptuous as vol

FAKE_HA_SESSION = object()
REDACTED = "**REDACTED**"


class AbortFlow(Exception):
    """Test stub for Home Assistant's AbortFlow exception."""

    def __init__(self, reason: str, data: dict[str, Any] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.data = data


def _install_homeassistant_stubs() -> None:
    """Install lightweight Home Assistant module stubs when HA Core is not installed."""
    if importlib.util.find_spec("homeassistant") is not None:
        return

    ha_mod = types.ModuleType("homeassistant")
    ha_ce = types.ModuleType("homeassistant.config_entries")
    ha_const = types.ModuleType("homeassistant.const")
    ha_core = types.ModuleType("homeassistant.core")
    ha_exc = types.ModuleType("homeassistant.exceptions")
    ha_helpers = types.ModuleType("homeassistant.helpers")
    ha_aiohttp = types.ModuleType("homeassistant.helpers.aiohttp_client")
    ha_dr = types.ModuleType("homeassistant.helpers.device_registry")
    ha_ep = types.ModuleType("homeassistant.helpers.entity_platform")
    ha_sel = types.ModuleType("homeassistant.helpers.selector")
    ha_uc = types.ModuleType("homeassistant.helpers.update_coordinator")
    ha_comp = types.ModuleType("homeassistant.components")
    ha_diag = types.ModuleType("homeassistant.components.diagnostics")
    ha_select = types.ModuleType("homeassistant.components.select")
    ha_sensor = types.ModuleType("homeassistant.components.sensor")
    ha_wh = types.ModuleType("homeassistant.components.water_heater")

    ha_ce.SOURCE_USER = "user"
    ha_ce.SOURCE_REAUTH = "reauth"
    ha_ce.SOURCE_RECONFIGURE = "reconfigure"
    ha_ce.ConfigFlowResult = dict

    class StubConfigEntry:
        """Minimal ConfigEntry supporting generic runtime_data."""

        def __class_getitem__(cls, item: Any) -> type[StubConfigEntry]:
            return cls

        def __init__(
            self,
            *,
            entry_id: str = "entry-1",
            version: int = 1,
            unique_id: str | None = "acct-123",
            data: dict[str, Any] | None = None,
        ) -> None:
            self.entry_id = entry_id
            self.version = version
            self.unique_id = unique_id
            self.data = data or {}
            self.runtime_data: Any = None
            self.async_start_reauth = MagicMock()

    class StubConfigFlow:
        """Minimal ConfigFlow test harness."""

        def __init_subclass__(cls, domain: str | None = None, **kwargs: Any) -> None:
            cls.DOMAIN = domain

        def __init__(self) -> None:
            self.hass = MagicMock()
            self.source = ha_ce.SOURCE_USER
            self.unique_id: str | None = None
            self._existing_unique_ids: set[str] = set()
            self._reauth_entry = StubConfigEntry(
                unique_id="acct-123",
                data={"email": "u@example.com", "password": "old", "refresh_token": "old"},
            )
            self._reconfigure_entry = StubConfigEntry(
                unique_id="acct-123",
                data={"email": "u@example.com", "password": "old", "refresh_token": "old"},
            )

        def async_show_form(
            self,
            *,
            step_id: str,
            data_schema: Any = None,
            errors: dict[str, str] | None = None,
            description_placeholders: dict[str, str] | None = None,
        ) -> dict[str, Any]:
            return {
                "type": "form",
                "step_id": step_id,
                "data_schema": data_schema,
                "errors": errors or {},
                "description_placeholders": description_placeholders or {},
            }

        def add_suggested_values_to_schema(
            self, data_schema: Any, suggested_values: Mapping[str, Any]
        ) -> Any:
            return data_schema

        async def async_set_unique_id(self, unique_id: str) -> None:
            self.unique_id = unique_id

        def _abort_if_unique_id_configured(self, updates: dict[str, Any] | None = None) -> None:
            if self.unique_id in self._existing_unique_ids:
                raise AbortFlow("already_configured", data=updates)

        def _abort_if_unique_id_mismatch(self, *, reason: str = "wrong_account") -> None:
            target = (
                self._reconfigure_entry
                if self.source == ha_ce.SOURCE_RECONFIGURE
                else self._reauth_entry
            )
            if self.unique_id != target.unique_id:
                raise AbortFlow(reason)

        def _get_reauth_entry(self) -> StubConfigEntry:
            return self._reauth_entry

        def _get_reconfigure_entry(self) -> StubConfigEntry:
            return self._reconfigure_entry

        def async_update_reload_and_abort(
            self, entry: StubConfigEntry, *, data: dict[str, Any]
        ) -> dict[str, Any]:
            reason = (
                "reconfigure_successful"
                if self.source == ha_ce.SOURCE_RECONFIGURE
                else "reauth_successful"
            )
            return {"type": "abort", "reason": reason, "data": data}

        def async_create_entry(self, *, title: str, data: dict[str, Any]) -> dict[str, Any]:
            return {"type": "create_entry", "title": title, "data": data}

    ha_ce.ConfigEntry = StubConfigEntry
    ha_ce.ConfigFlow = StubConfigFlow
    ha_mod.config_entries = ha_ce

    ha_const.ATTR_TEMPERATURE = "temperature"
    ha_const.CONF_EMAIL = "email"
    ha_const.CONF_PASSWORD = "password"
    ha_const.PRECISION_WHOLE = 1
    ha_const.UnitOfTemperature = MagicMock(FAHRENHEIT="°F")
    ha_const.UnitOfEnergy = MagicMock(KILO_WATT_HOUR="kWh")

    class Platform:
        SELECT = "select"
        SENSOR = "sensor"
        WATER_HEATER = "water_heater"

    ha_const.Platform = Platform
    ha_core.HomeAssistant = object
    ha_core.callback = lambda fn: fn

    class ConfigEntryAuthFailed(Exception):
        pass

    class ConfigEntryNotReady(Exception):
        pass

    class HomeAssistantError(Exception):
        pass

    class ServiceValidationError(HomeAssistantError):
        pass

    ha_exc.ConfigEntryAuthFailed = ConfigEntryAuthFailed
    ha_exc.ConfigEntryNotReady = ConfigEntryNotReady
    ha_exc.HomeAssistantError = HomeAssistantError
    ha_exc.ServiceValidationError = ServiceValidationError

    ha_aiohttp.async_get_clientsession = MagicMock(return_value=FAKE_HA_SESSION)
    ha_dr.DeviceInfo = dict
    ha_ep.AddEntitiesCallback = object

    class TextSelectorType:
        EMAIL = "email"
        PASSWORD = "password"

    class TextSelectorConfig(dict):
        pass

    class TextSelector:
        def __init__(self, config: TextSelectorConfig | None = None) -> None:
            self.config = config or TextSelectorConfig()

        def __call__(self, value: Any) -> str:
            if not isinstance(value, str):
                raise vol.Invalid("Expected string")
            return value

    ha_sel.TextSelectorType = TextSelectorType
    ha_sel.TextSelectorConfig = TextSelectorConfig
    ha_sel.TextSelector = TextSelector

    class DataUpdateCoordinator:
        def __class_getitem__(cls, item: Any) -> type[DataUpdateCoordinator]:
            return cls

        def __init__(
            self,
            hass: Any,
            logger: Any,
            *,
            config_entry: Any = None,
            name: str,
            update_interval: Any,
        ) -> None:
            self.hass = hass
            self.logger = logger
            self.config_entry = config_entry
            self.name = name
            self.update_interval = update_interval
            self.data: Any = None
            self.last_update_success = True
            self._listeners: list[Callable[[], None]] = []

        def async_add_listener(
            self, update_callback: Callable[[], None], context: Any = None
        ) -> Callable[[], None]:
            self._listeners.append(update_callback)

            def _unsub() -> None:
                if update_callback in self._listeners:
                    self._listeners.remove(update_callback)

            return _unsub

        def _notify_listeners(self) -> None:
            for listener in list(self._listeners):
                listener()

        def async_set_updated_data(self, data: Any) -> None:
            self.data = data
            self.last_update_success = True
            self._notify_listeners()

        async def async_config_entry_first_refresh(self) -> None:
            self.data = await self._async_update_data()
            self.last_update_success = True
            self._notify_listeners()

        async def async_request_refresh(self) -> None:
            self.data = await self._async_update_data()
            self.last_update_success = True
            self._notify_listeners()

    class CoordinatorEntity:
        def __class_getitem__(cls, item: Any) -> type[CoordinatorEntity]:
            return cls

        def __init__(self, coordinator: DataUpdateCoordinator) -> None:
            self.coordinator = coordinator
            self.hass = getattr(coordinator, "hass", None)

        async def async_added_to_hass(self) -> None:
            parent = getattr(super(), "async_added_to_hass", None)
            if parent is not None:
                await parent()
            self.coordinator.async_add_listener(self._handle_coordinator_update)

        @property
        def available(self) -> bool:
            return bool(self.coordinator.last_update_success)

        def _handle_coordinator_update(self) -> None:
            pass

    class UpdateFailed(Exception):
        pass

    ha_uc.DataUpdateCoordinator = DataUpdateCoordinator
    ha_uc.CoordinatorEntity = CoordinatorEntity
    ha_uc.UpdateFailed = UpdateFailed

    def async_redact_data(data: Any, to_redact: Iterable[Any]) -> Any:
        redact_set = set(to_redact)
        if isinstance(data, Mapping):
            return {
                key: (REDACTED if key in redact_set else async_redact_data(val, redact_set))
                for key, val in data.items()
            }
        if isinstance(data, list):
            return [async_redact_data(item, redact_set) for item in data]
        return data

    ha_diag.REDACTED = REDACTED
    ha_diag.async_redact_data = async_redact_data

    class SelectEntity:
        _attr_options: list[str]

        @property
        def options(self) -> list[str]:
            return self._attr_options

        async def async_added_to_hass(self) -> None:
            pass

    ha_select.SelectEntity = SelectEntity

    @dataclass
    class RestoredSensorData:
        native_value: Any

    class RestoreSensor:
        _restored_sensor_data: RestoredSensorData | None = None

        async def async_added_to_hass(self) -> None:
            pass

        async def async_get_last_sensor_data(self) -> RestoredSensorData | None:
            return self._restored_sensor_data

    ha_sensor.SensorDeviceClass = MagicMock(ENERGY="energy")
    ha_sensor.SensorStateClass = MagicMock(TOTAL_INCREASING="total_increasing")
    ha_sensor.RestoreSensor = RestoreSensor
    ha_sensor.RestoredSensorData = RestoredSensorData

    ha_wh.STATE_ECO = "eco"
    ha_wh.STATE_ELECTRIC = "electric"
    ha_wh.STATE_HEAT_PUMP = "heat_pump"
    ha_wh.STATE_HIGH_DEMAND = "high_demand"
    ha_wh.STATE_OFF = "off"

    class WaterHeaterEntityFeature:
        TARGET_TEMPERATURE = 1
        OPERATION_MODE = 2
        AWAY_MODE = 4

    class WaterHeaterEntity:
        async def async_added_to_hass(self) -> None:
            pass

    ha_wh.WaterHeaterEntityFeature = WaterHeaterEntityFeature
    ha_wh.WaterHeaterEntity = WaterHeaterEntity

    for name, module in {
        "homeassistant": ha_mod,
        "homeassistant.config_entries": ha_ce,
        "homeassistant.const": ha_const,
        "homeassistant.core": ha_core,
        "homeassistant.exceptions": ha_exc,
        "homeassistant.helpers": ha_helpers,
        "homeassistant.helpers.aiohttp_client": ha_aiohttp,
        "homeassistant.helpers.device_registry": ha_dr,
        "homeassistant.helpers.entity_platform": ha_ep,
        "homeassistant.helpers.selector": ha_sel,
        "homeassistant.helpers.update_coordinator": ha_uc,
        "homeassistant.components": ha_comp,
        "homeassistant.components.diagnostics": ha_diag,
        "homeassistant.components.select": ha_select,
        "homeassistant.components.sensor": ha_sensor,
        "homeassistant.components.water_heater": ha_wh,
    }.items():
        sys.modules[name] = module


_install_homeassistant_stubs()

from bradford_white_wave_client import BradfordWhiteMode, DeviceStatus, EnergyUsage  # noqa: E402


@pytest.fixture
def sample_summary_device() -> DeviceStatus:
    """Return a DeviceStatus shaped like /wave/getApplianceList."""
    return DeviceStatus.model_validate(
        {
            "macAddress": "AA:BB:CC:DD:EE:FF",
            "friendlyName": "Home",
            "serialNumber": "BJ55834840",
            "applianceType": "AeroTherm G2",
            "accessLevel": 1,
        }
    )


@pytest.fixture
def sample_detailed_device() -> DeviceStatus:
    """Return a DeviceStatus shaped like /wave/getApplianceStatus (without applianceType)."""
    return DeviceStatus.model_validate(
        {
            "macAddress": "AA:BB:CC:DD:EE:FF",
            "friendlyName": "Home",
            "serialNumber": "BJ55834840",
            "setpointFahrenheit": 120,
            "heatModeValue": int(BradfordWhiteMode.HYBRID),
            "requestId": "req-999",
        }
    )


@pytest.fixture
def sample_energy_point() -> EnergyUsage:
    """Return a sample EnergyUsage record."""
    return EnergyUsage(
        timestamp=datetime(2026, 11, 13, 0, 0),
        total_energy=12.45,
        heat_pump_energy=11.95,
        element_energy=0.50,
        reported_minutes=1440,
    )
