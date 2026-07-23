# Development Index

This folder contains the development documentation for the project.

## Read First

0. `../README.md`
1. `docs/overview.md`
2. `docs/domain-model.md`
3. `docs/scoring-model.md`
4. `docs/home-assistant-integration.md`
5. `docs/project-rules.md`
6. `docs/testing.md`
7. `docs/development.md`
8. `docs/hacs-packaging.md`
9. `docs/NOTICE.md`

## Purpose

The project is intended to become:

- a reusable Python comfort engine
- a Home Assistant custom integration
- a HACS-installable package

## Development Rules

- Keep the core engine independent from Home Assistant APIs.
- Keep room configuration in HA config entries, not hardcoded in Python.
- Keep the UI as the primary configuration path.
- Keep the logic bidirectional: summer and winter must both work.
- Keep anti-spam behavior central to the design.
- Keep the backlog only in GitHub issues; do not duplicate it in the repo.
