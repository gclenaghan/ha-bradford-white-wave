# Bradford White Wave Home Assistant Integration

This integration provides support for [Bradford White Water Heaters](https://www.bradfordwhite.com/) that use the "Wave" platform (e.g. AeroTherm G2).

Older models use the "Connect" platform and are supported by the [bradford-white-connect](https://github.com/ablyler/home-assistant-bradford-white-connect) integration, which this integration is based on.

## Features

- Control Operation Mode (Hybrid, Hybrid Plus, Heat Pump, Electric, Vacation)
- Control Setpoint Temperature (100–140 °F)
- Energy Usage Sensors (Total, Heat Pump, Element) broken down by:
  - Weekly
  - Monthly

## Requirements

- Home Assistant **2026.11.0** or newer.

## Installation

### Marketplace / HACS (Recommended)

1. Open **Settings -> Marketplace** (or **HACS**).
2. Search for **Bradford White Wave**.
3. Click **Download** / **Install**.
4. Restart Home Assistant.

### Manual

1. Copy the `custom_components/bradford_white_wave` directory to your `config/custom_components` directory.
2. Restart Home Assistant.

## Configuration

1. Go to **Settings -> Devices & Services**.
2. Click **+ ADD INTEGRATION**.
3. Search for **Bradford White Wave**.
4. Enter your Bradford White Wave email address and password.

## Entities

### Water Heater

- `water_heater.<device_name>`: Standard Home Assistant water heater controls for operation mode and target temperature.
  - **Note**: The API does _not_ report the current tank temperature, so the entity will not show a current temperature value.

| Mode in Bradford White Wave App | Mode Displayed in Home Assistant | `water_heater.set_operation_mode` Value |
| :--- | :--- | :--- |
| **Hybrid** | Eco | `eco` |
| **Hybrid Plus** | High demand | `high_demand` |
| **Heat Pump** | Heat pump | `heat_pump` |
| **Electric** | Electric | `electric` |
| **Vacation** | Off | `off` |

### Sensors

- `sensor.<device_name>_monthly_total_energy`: Monthly total energy (kWh)
- `sensor.<device_name>_monthly_heat_pump_energy`: Monthly heat pump energy (kWh)
- `sensor.<device_name>_monthly_element_energy`: Monthly element energy (kWh)
- `sensor.<device_name>_weekly_total_energy`: Weekly total energy (kWh)
- `sensor.<device_name>_weekly_heat_pump_energy`: Weekly heat pump energy (kWh)
- `sensor.<device_name>_weekly_element_energy`: Weekly element energy (kWh)

Hourly and daily sensors are not currently enabled since they were found to be unreliable in testing.

## Disclaimer

- This is an unofficial integration and is not affiliated with Bradford White.
- Tested with an AeroTherm G2.
