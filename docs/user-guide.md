# VentWise User Guide

VentWise is a Home Assistant custom integration that suggests when opening or
closing windows may improve indoor comfort. It is beta software and provides
recommendations only: always check the actual conditions before acting. Read
the [safety notice](NOTICE.md) before using it in a real home.

## Before You Start

You need a working Home Assistant installation and at least one Home Assistant
`weather` entity. For useful room-level recommendations, prepare one indoor
temperature sensor and one indoor humidity sensor for each room you want to
configure.

VentWise does not open or close windows, change a thermostat, or replace a
safety, weather-protection, or security system.

## Install with HACS

This is the easiest installation method when HACS is already installed.

[![Add VentWise to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=AlexSantini10&repository=ventwise&category=integration)

1. Open the button from a device and browser that can reach your Home Assistant instance.
2. Let HACS add or open the VentWise custom repository.
3. Select **Download** and choose the latest stable release.
4. Restart Home Assistant if HACS asks you to do so.
5. Go to **Settings > Devices & services > Add integration**, search for **VentWise**, and complete the setup.

VentWise can be installed this way before it appears in HACS's public catalogue.
HACS still asks for your confirmation; the button never installs or restarts
anything silently.

## Manual Installation

Use this method when you do not use HACS.

1. Download `ventwise.zip` from the [latest GitHub release](https://github.com/AlexSantini10/ventwise/releases/latest).
2. In your Home Assistant configuration directory, create this path if it does not already exist:

   ```text
   custom_components/ventwise/
   ```

3. Extract the contents of `ventwise.zip` directly into that `ventwise` directory.
4. Restart Home Assistant.
5. Add **VentWise** from **Settings > Devices & services > Add integration**.

The Home Assistant configuration directory is commonly `/config` on Home
Assistant OS, the directory mounted as `/config` for Container installations,
and `~/.homeassistant` for Home Assistant Core. Use the directory configured
for your own installation if it differs.

## First Setup

The setup form asks for:

- a Home Assistant weather entity;
- your preferred indoor comfort temperature and humidity;
- whether to use the climate-adaptive comfort target;
- a stability delay before sending recommendations; and
- optional notification devices or Home Assistant persistent notifications.

After initial setup, open **Configure** on the VentWise integration to add a
room. Give it a clear name and select its indoor temperature and humidity
sensors. You can add, edit, disable, or remove rooms later from the same menu.

## Everyday Use

VentWise exposes its recommendation and supporting measurements through Home
Assistant entities. Check the recommendation before opening or closing a
window. A recommendation can be delayed by the configured stability period,
quiet hours, cooldown, missing data, or a disabled room.

Use **Configure** on the integration to change comfort values, notification
settings, weather source, outdoor-data overrides, quiet hours, or rooms. The
climate-adaptive option changes only VentWise's recommendation target; it does
not change a thermostat or HVAC setpoint.

## Update

With HACS, open VentWise in HACS and select **Update** when an update is
available, then restart Home Assistant if requested. With manual installation,
download the newer `ventwise.zip`, replace the integration files in
`custom_components/ventwise/`, and restart Home Assistant.

Back up your Home Assistant configuration before a manual update. VentWise
migrates its own stored configuration when needed; if a migration cannot be
performed safely, it keeps the entry unchanged and reports the problem in the
Home Assistant logs.

## Remove VentWise

1. Remove the VentWise integration entry from **Settings > Devices & services**.
2. If you used HACS, remove VentWise from HACS as well.
3. For a manual installation, delete only `custom_components/ventwise/` from
   your Home Assistant configuration directory.
4. Restart Home Assistant.

Removing the integration stops its recommendations. Review any automations,
dashboards, or notifications that refer to VentWise entities after removal.

## Get Help or Report a Problem

VentWise records setup failures, notification-delivery failures, and changes
in the availability of the data it needs in the Home Assistant log. Normal
recommendation changes, a disabled integration, and optional forecast data are
not errors. Log entries are deliberately limited to diagnostic context and do
not include credentials or sensor values, but Home Assistant logs can still
contain personal information from other integrations.

For a problem that is already visible, open **Settings > System > Logs** and
look for `VentWise` or `custom_components.ventwise`. Home Assistant retains a
short list of recent warnings and errors there, with a full raw log available
from the same page.

For a problem that needs more detail:

1. Go to **Settings > Devices & services**, open the VentWise integration, and
   use the three-dot menu to select **Enable debug logging**.
2. Reproduce the problem once, noting the approximate time.
3. Return to the same menu, select **Disable debug logging**, then download or
   copy the relevant log entries from **Settings > System > Logs**.

If the integration menu is unavailable, temporarily add this to
`configuration.yaml`, restart Home Assistant, reproduce the problem, then
remove the entry (or change it back to `warning`) and restart again:

```yaml
logger:
  logs:
    custom_components.ventwise: debug
```

Open a [GitHub issue](https://github.com/AlexSantini10/ventwise/issues) with:

- VentWise and Home Assistant versions;
- the weather and room sensor types involved, without their real names;
- clear steps to reproduce, expected behavior, actual behavior, and the time
  it occurred; and
- only the relevant, sanitized VentWise log lines and traceback.

Never publish credentials, access tokens, exact address information, device
identifiers, entity IDs that reveal personal details, complete configuration
files, or an unfiltered full Home Assistant log.
