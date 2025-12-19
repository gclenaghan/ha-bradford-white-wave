# Project Context: Bradford White Wave HA Integration

## Overview
This project is a Home Assistant integration for Bradford White water heaters using the new "Wave" platform (e.g., Aerotherm G2). It is distinct from the older "Connect" integration.

## Architecture
-   **Domain**: `bradford_white_wave`
-   **Client Library**: `bradford-white-wave-client` (Async, Pydantic models).
-   **Platforms**: `water_heater`, `sensor`.

## Key Implementation Details

### Authentication (Non-Standard)
The Wave API uses Azure AD B2C with a flow that is difficult to automate fully (CAPTCHA/browser challenges). We use a **semi-automated flow**:
1.  **Config Flow** generates an authorization URL.
2.  User opens URL, logs in, and gets redirected to a custom scheme (`com.bradfordwhiteapps.bwconnect://`).
3.  User copies this full redirect URL back into the Config Flow.
4.  Integration swaps the code for tokens and persists the `refresh_token`.
5.  Access tokens are auto-refreshed by the client library.

### Water Heater Entity
-   **Current Temperature**: The API **does not** report the current tank temperature in the standard status payload. We have explicitly **removed** the `current_temperature` property to avoid confusion or errors.
-   **Controls**: Supports Setpoint (100-140°F) and Operation Mode (Hybrid, Heat Pump, Electric, Vacation).
-   **Polling**: Default is 60s. Switches to "Fast Interval" (10s) immediately after a control action to verify changes quickly.

### Energy Sensors
-   **Data Sources**: The API provides detailed energy usage for `hourly`, `daily`, `weekly`, and `monthly` views.
-   **Entities**: We create separate sensor entities for each view type and energy component (Total, Heat Pump, Element).
-   **Update Interval**: 5 minutes (user requested).

## Current Status
-   **Codebase**: Complete skeleton and core logic implemented in `custom_components/bradford_white_wave`.
-   **Verification**: Code passes `py_compile` checks.
-   **Testing**: Needs verification with a real device/account to confirm API responses match assumptions (especially around exact field names and nullability).

## Next Steps
1.  **Manual Verification**: Use `walkthrough.md` steps to test with a real, live HA instance and water heater.
2.  **Error Handling**: Refine error handling if the API returns unexpected structures (e.g. empty lists for energy).
3.  **HACS Support**: Ensure repository structure is compatible with HACS (it appears so).
