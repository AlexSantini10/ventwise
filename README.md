# VentWise

<p align="center">
  <img src="https://raw.githubusercontent.com/AlexSantini10/ventwise/main/docs/assets/brand/banner.png" alt="VentWise banner" width="960" />
</p>

<p align="center">
  <a href="https://github.com/AlexSantini10/ventwise/releases/latest">
    <img src="https://img.shields.io/github/v/release/AlexSantini10/ventwise?display_name=tag&logo=git&logoColor=white&style=for-the-badge" alt="Latest release" />
  </a>
  <a href="https://github.com/AlexSantini10/ventwise/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/AlexSantini10/ventwise/ci.yml?branch=main&label=CI&logo=githubactions&style=for-the-badge" alt="CI status" />
  </a>
  <a href="https://hacs.xyz/">
    <img src="https://img.shields.io/badge/HACS-Default-orange.svg?logo=HomeAssistantCommunityStore&logoColor=white&style=for-the-badge" alt="HACS Default" />
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/github/license/AlexSantini10/ventwise?logo=apache&logoColor=white&style=for-the-badge" alt="Apache-2.0 license" />
  </a>
  <a href="https://www.home-assistant.io/integrations/">
    <img src="https://img.shields.io/badge/Home%20Assistant-Integration-41BDF5?logo=homeassistant&logoColor=white&style=for-the-badge" alt="Home Assistant integration" />
  </a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white&style=for-the-badge" alt="Python 3.11 or later" />
  <img src="https://img.shields.io/github/downloads/AlexSantini10/ventwise/total?label=Downloads&style=for-the-badge" alt="Downloads" />
  <img src="https://img.shields.io/github/stars/AlexSantini10/ventwise?label=Stars&color=darkgoldenrod&style=for-the-badge" alt="Stars" />
</p>

**A Home Assistant custom integration for weather-aware window ventilation and
indoor-comfort recommendations.**

VentWise helps users decide when opening or closing windows is likely to improve indoor comfort. It evaluates a standard weather source, optional outdoor temperature, humidity, and wind overrides, and the configured comfort target, then exposes a clear recommendation back to Home Assistant.

> [!WARNING]
> **Beta software - use recommendations with care.** VentWise has automated CI
> coverage and limited real-world use, but it has not been exhaustively tested
> across all homes, sensors, weather conditions, or hardware. It provides
> informational recommendations only; it is not a safety, security, weather-
> protection, or automation-control system. Optional room automations require
> an explicit Companion App notification confirmation. Always assess the actual conditions
> before opening or closing anything, and do not rely on VentWise to prevent
> injury, property damage, intrusion, rain exposure, or equipment damage. See
> the full [license, disclaimer, and reporting guidance](docs/NOTICE.md).

## At a glance

- Comfort-based recommendation engine
- Multi-room support
- Room management from the Home Assistant UI
- Summer and winter behavior
- Quiet hours and cooldowns
- Persisted runtime state across restarts
- HACS-ready packaging

## Installation

VentWise is available in the **default HACS catalogue**; no custom repository
is needed.

1. Open **HACS** in Home Assistant and select **Integrations**.
2. Search for **VentWise**, open it, and select **Download**.
3. Restart Home Assistant when prompted.
4. Open **Settings > Devices & services > Add integration**, then select
   **VentWise** to configure it.

Stable releases are published from `main`. Experimental prereleases from the
`test` branch family are for testing only.

## Documentation

- [User guide: installation, setup, updates, and removal](docs/user-guide.md)
- [Docker Test Lab: local manual testing without hardware](docs/docker-test-lab.md)
- [How the Home Assistant integration works](docs/home-assistant-integration.md)
- [Safety, beta status, and reporting guidance](docs/NOTICE.md)
- [Contributing guide](CONTRIBUTING.md)
- [Documentation index](docs/INDEX.md)

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](docs/NOTICE.md).
