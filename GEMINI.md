# Project Context: Bradford White Wave HA Integration

## Overview

This project is a Home Assistant integration for Bradford White water heaters using the "Wave" platform (e.g., AeroTherm G2). It is distinct from the older "Connect" integration.

## Architecture

- **Domain**: `bradford_white_wave`
- **Client Library**: `bradford-white-wave-client` (`>=1.0.0`, Async, Pydantic v2 models).
- **Platforms**: `water_heater`, `sensor`.

## Key Implementation Details

### Authentication

- **Setup (`async_step_user`)**: Collects `email` and `password`, authenticates directly against Bradford White's Azure AD B2C policy (`B2C_1_Wave_SignIn`) via `client.authenticate_with_credentials()` using Home Assistant's shared `aiohttp` session (`async_get_clientsession(hass)`), and persists `email`, `password`, and `refresh_token` in `entry.data`.
- **Runtime Refresh & Auto-Recovery**: Day-to-day polling uses `refresh_token` via OAuth `/token` and persists rotated refresh tokens automatically via `on_token_update`. If `refresh_token` expires (e.g., Azure AD B2C's 90-day sliding window cap), `BradfordWhiteClient` automatically re-authenticates using the stored `email` and `password`.
- **Reauthentication & Reconfiguration (`async_step_reauth`, `async_step_reconfigure`)**: `async_step_reauth` triggers via `ConfigEntryAuthFailed` if stored credentials fail (e.g., password changed in the Wave app or legacy `1.0.x` entry without stored credentials); `async_step_reconfigure` lets users update credentials proactively from the integration menu.

### Water Heater Entity

- **Current Temperature**: The API **does not** report the current tank temperature in the standard status payload. `current_temperature` is omitted intentionally.
- **Controls**: Supports Setpoint (100-140°F) and Operation Mode (Hybrid, Hybrid Plus, Heat Pump, Electric, Vacation).
- **Polling**: Default is 60s. Switches to "Fast Interval" (10s) immediately after a control action to verify changes quickly.

### Energy Sensors

- **Data Sources**: Weekly and monthly energy usage views (hourly/daily omitted as unreliable).
- **Entities**: Separate sensor entities for each enabled view type and energy component (Total, Heat Pump, Element).
- **Update Interval**: 5 minutes.
