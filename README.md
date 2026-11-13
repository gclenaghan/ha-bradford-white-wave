# Bradford White Wave Home Assistant Integration

This integration provides support for [Bradford White Water Heaters](https://www.bradfordwhite.com/) that use the "Wave" platform (e.g. AeroTherm G2).

Older models use the "Connect" platform and are supported by the [bradford-white-connect](https://github.com/ablyler/home-assistant-bradford-white-connect) integration, which this integration is based on.

## Features

- Control Operation Mode (Hybrid, Hybrid Plus, Heat Pump, Electric, Vacation)
- Control Setpoint Temperature
- Sensor for current Operation Mode
- Energy Usage Sensors (Total, Heat Pump, Element) broken down by:
  - Weekly
  - Monthly

## Installation

### Marketplace / HACS (Recommended)

1. Open **Settings -> Marketplace** (or **HACS** on Home Assistant < 2026.11).
2. Click the three dots in the top right and select **Custom repositories**.
3. Add `https://github.com/gclenaghan/ha-bradford-white-wave` with category **Integration**, then click **Add**.
4. Find **Bradford White Wave** and click **Download** / **Install**.
5. Restart Home Assistant.

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

- `water_heater.device_name`: Controls for mode and temperature.
  - **Note**: The API does _not_ report the current tank temperature, so the entity will not show a current temperature value.

### Sensors

- `sensor.device_name_energy_monthly_total`: Monthly total energy (kWh)
- `sensor.device_name_energy_monthly_heat_pump`: Monthly heat pump energy (kWh)
- `sensor.device_name_energy_monthly_element`: Monthly element energy (kWh)
- `sensor.device_name_energy_weekly_total`: Weekly total energy (kWh)
- `sensor.device_name_energy_weekly_heat_pump`: Weekly heat pump energy (kWh)
- `sensor.device_name_energy_weekly_element`: Weekly element energy (kWh)

Hourly and daily sensors are not currently enabled since they were found to be unreliable in testing.

## Disclaimer

- This is an unofficial integration and is not affiliated with Bradford White.
- Tested with an AeroTherm G2.
