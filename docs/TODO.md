# TODO

The actionable backlog lives in GitHub issues. This page is a compact map of
the current product work so the repo stays readable at a glance.

## Product Backlog

- Room setup and per-room configuration from the Home Assistant UI
- Comfort temperature and all entity selectors from the Home Assistant UI
- Notification targets and device selection
- Do-not-disturb controls, quiet hours, and temporary notification blocks
- Core comfort scoring for summer and winter
- Home Assistant entities for recommendation, score, and reason
- Testing coverage for warm, cold, neutral, and spam-suppression scenarios
- Packaging, CI, and release automation

## Notes

- Keep each issue at a functional size, roughly one feature per issue.
- Keep the core independent from Home Assistant APIs.
- Keep the integration UI-first, without manual YAML for normal use.
