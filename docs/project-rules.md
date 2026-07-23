# Project Rules

This document collects the working rules and product decisions that should stay
stable over time. It is derived from the project docs, the issue backlog, and
the implementation decisions agreed during development.

## Core Principles

- Keep the Home Assistant UI as the primary configuration path.
- Avoid manual YAML for normal setup and day-to-day changes.
- Keep the reusable scoring core independent from Home Assistant APIs.
- Keep the repository backlog in GitHub issues, not duplicated as TODO lists in
  the repo.
- Keep the UX understandable for non-technical users.

## User-Facing UI Rules

- Every user-facing field must have a clear human-readable label.
- Every user-facing field must have a short explanation when the meaning is not
  obvious.
- Every user-facing string must be translated.
- Keep `en.json` complete and treat it as the fallback source of truth for all
  locales.
- If a locale file or a specific key is missing, Home Assistant must fall back
  to English automatically.
- When a UI element is added, it must be added once, with one clear source of
  truth.
- Do not keep legacy UI residues after replacing a setting or flow.
- Prefer one obvious control for each setting.
- The only allowed exception is a global setting that may also accept a room
  override.
- If a setting is optional, keep it optional.
- If a setting can be provided by the integration itself, do not force the user
  to create helpers manually.
- Helper entities created by the integration should be exposed in a simple and
  understandable way.

## Setup Flow Rules

- The setup flow should stay short, readable, and approachable.
- Initial setup should collect only the minimum needed to make VentWise work.
- Post-setup settings should be grouped by purpose, not by internal technical
  details.
- Rooms and macro-rooms should be configurable from the UI.
- A room can be added during the initial setup, but it must not be required.
- Supported forecast sources should be explicit in the UI.
- Unsupported forecast sources should be requested through GitHub issues.

## Entity Exposure Rules

- Expose one global VentWise device for shared controls and global sensors.
- Expose one device per room or macro-room for room-specific entities.
- Keep entity names descriptive and non-technical.
- Expose useful controls and sensors, but avoid exposing noise that does not
  help the user act.
- Global controls remain global by default.
- Room overrides are allowed only where they add real value.

## Data Flow Rules

- Prefer event-driven updates whenever possible.
- Entity state changes should refresh the integration immediately.
- Avoid periodic polling unless a small time-based refresh is required.
- Time-based refreshes are allowed for gates such as stability windows,
  cooldowns, and quiet hours.
- Do not introduce fixed polling loops for internal state propagation when an
  entity change or config change can trigger a refresh instead.

## Recommendation Rules

- Base the recommendation on perceived temperature, not raw temperature alone.
- Perceived temperature must consider humidity.
- Open/close recommendations should be produced only when they create a
  meaningful advantage.
- If the gain is too small, return `none`.
- The recommendation score and the recommendation action are different things.
- The score expresses strength or confidence.
- The action expresses what the user should do.
- Notification cooldown must affect notifications only.
- Recommendation logic must keep working even when notifications are in
  cooldown.
- A master enable must disable the whole integration.
- A notification enable must control notifications only.
- Quiet hours must suppress notifications and recommendation delivery, not the
  underlying ability to compute the state.

## Comfort Rules

- Comfort temperature is the global baseline comfort target.
- Rooms may override the comfort target if that is useful.
- Comfort humidity can also be configured.
- The stability window should be configured in the initial setup.
- If the user is unsure about the stability window, the default should be kept.
- Outdoor data can come either from the forecast or from manual numeric
  overrides.
- Outdoor manual overrides should be enabled with checkboxes and only then ask
  for the corresponding numeric entity.

## Room Rules

- A room must expose its own indoor sensors and room-specific recommendation
  data.
- Room-level temperature and humidity sensors should be exposed when available.
- Room-specific comfort overrides are allowed for temperature and humidity.
- Room automations should be limited to opening and closing actions.
- Do not keep old automation patterns that are no longer part of the product
  model.

## Release Rules

- The integration release version is driven by `custom_components/ventwise/manifest.json`.
- To create a new release, update the manifest version and let the release
  workflow publish from that value.
- Stable releases are published from `main`.
- Experimental prereleases are published from the `test` branch family.
- Repositories should stay clean and reproducible for releases.

## Maintenance Rules

- Keep tests aligned with the current runtime API.
- Remove obsolete constants, flow steps, and translations when the product
  model changes.
- If a new UI setting is added, add translations and documentation at the same
  time.
- If a new scoring rule is added, add a focused regression test.
- If a new product decision is made in chat or an issue, record it here once it
  becomes a stable rule.

## Operational Checklist

Use this checklist before merging any change:

- [ ] The change is tracked by a GitHub issue, or it is a direct follow-up to
      an existing issue.
- [ ] The user-facing wording is human-readable.
- [ ] Every new UI field has a short description if needed.
- [ ] Every new UI string has translations.
- [ ] `en.json` stays complete and all locale files fall back to English.
- [ ] No old UI residue remains in the flow or entity labels.
- [ ] There is one clear source of truth for every setting.
- [ ] The UI stays consistent with the product model.
- [ ] Optional fields stay optional.
- [ ] Global settings and room overrides are the only intentional duplicate
      control path.
- [ ] The setup flow remains short and understandable.
- [ ] The flow only asks for entities or helpers when they are actually needed.
- [ ] Outdoor manual overrides use checkboxes to unlock the numeric selectors.
- [ ] Room and macro-room settings remain separate from global settings.
- [ ] Entity names are descriptive for non-technical users.
- [ ] Global and room entities are exposed in the expected device structure.
- [ ] The data flow is event-driven wherever possible.
- [ ] Only stability, cooldown, and quiet-hours checks may rely on time-based
      refreshes.
- [ ] Recommendations are based on perceived temperature, not raw temperature
      alone.
- [ ] Humidity is considered in the recommendation model.
- [ ] The recommendation only returns `open` or `close` when the gain is
      meaningful.
- [ ] If the gain is small, the result is `none`.
- [ ] Notification cooldown affects notifications only.
- [ ] Master enable disables the whole integration.
- [ ] Notification enable only controls notification delivery.
- [ ] Quiet hours block notification delivery, not the entire scoring engine.
- [ ] Every new scoring rule has a regression test.
- [ ] Every bug fix that changes behavior has a regression test.
- [ ] Tests still reflect the current runtime API.
- [ ] The repo tree stays clean after the change.
- [ ] Release-related changes update the manifest-driven versioning flow.

## PR / Merge Checklist

Before opening or merging a PR:

- [ ] `git status` is clean except for the intended change.
- [ ] The relevant unit tests pass locally.
- [ ] The relevant integration or runtime tests pass locally when available.
- [ ] `py_compile` or equivalent syntax checks pass for touched Python files.
- [ ] The docs that describe the changed behavior are updated.
- [ ] The issue list is updated if the change closes or splits work.
- [ ] Any obsolete branch, step, constant, or translation has been removed.
- [ ] The commit message is Conventional Commits style.
- [ ] The change has been reviewed for readable UI text and translations.
- [ ] The change has been reviewed for event-driven behavior and storage
      consistency.

## Related Sources

- `docs/ARCHITECTURE.md`
- `docs/home-assistant-integration.md`
- `docs/scoring-model.md`
- `docs/development.md`
- GitHub issues `#16`, `#22`, `#23`, `#49`, `#50`, `#51`, `#52`, `#53`, `#54`, `#61`, `#62`, `#63`
