"""Diagnostics support for Bradford White Wave."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import CONF_REFRESH_TOKEN
from .coordinator import BradfordWhiteConfigEntry

TO_REDACT: set[str] = {
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    "account_id",
    "mac_address",
    "macAddress",
    "serial_number",
    "serialNumber",
    "request_id",
    "requestId",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BradfordWhiteConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for a Bradford White Wave config entry."""
    runtime_data = entry.runtime_data
    status_coordinator = runtime_data.status_coordinator
    energy_coordinator = runtime_data.energy_coordinator

    devices_summary: dict[str, Any] = {}
    mac_to_alias: dict[str, str] = {}
    for index, (mac, device) in enumerate((status_coordinator.data or {}).items(), start=1):
        alias = f"device_{index}"
        mac_to_alias[mac] = alias
        devices_summary[alias] = device.model_dump(mode="json")

    energy_summary: dict[str, Any] = {}
    for index, (mac, views) in enumerate((energy_coordinator.data or {}).items(), start=1):
        alias = mac_to_alias.get(mac, f"energy_device_{index}")
        energy_summary[alias] = {
            view_name: [point.model_dump(mode="json") for point in points]
            for view_name, points in views.items()
        }

    diagnostics_payload: dict[str, Any] = {
        "entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "data": dict(entry.data),
        },
        "client": {
            "has_access_token": runtime_data.client.access_token is not None,
            "has_refresh_token": runtime_data.client.refresh_token is not None,
        },
        "status_coordinator": {
            "last_update_success": status_coordinator.last_update_success,
            "update_interval_seconds": (
                status_coordinator.update_interval.total_seconds()
                if status_coordinator.update_interval
                else None
            ),
            "devices": devices_summary,
        },
        "energy_coordinator": {
            "last_update_success": energy_coordinator.last_update_success,
            "update_interval_seconds": (
                energy_coordinator.update_interval.total_seconds()
                if energy_coordinator.update_interval
                else None
            ),
            "energy": energy_summary,
        },
    }

    return async_redact_data(diagnostics_payload, TO_REDACT)
