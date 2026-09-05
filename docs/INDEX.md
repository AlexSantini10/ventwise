# VentWise Documentation

Start with the document for your role.

## Using VentWise

1. [README](../README.md) for the short introduction and HACS button.
2. [User guide](user-guide.md) for installation, first setup, updates, and removal.
3. [Home Assistant integration](home-assistant-integration.md) for the configured data and entities.
4. [Notice](NOTICE.md) for beta status, safe use, and defect reporting.

## Contributing to VentWise

1. [Contributing guide](../CONTRIBUTING.md) for issues, branches, and pull requests.
2. [Development workflow](development.md) for local setup and common commands.
3. [Testing](testing.md) for the test layers and Home Assistant sandbox.
4. [Architecture](ARCHITECTURE.md), [domain model](domain-model.md), and [scoring model](scoring-model.md) for design details.
5. [HACS packaging](hacs-packaging.md) for releases, discovery, and packaging.
6. [Brand assets](brand-assets.md) for Home Assistant and repository artwork.

## Purpose

The project is intended to provide:

- a reusable Python comfort engine
- a Home Assistant custom integration
- a HACS-installable custom integration

## Development Rules

- Keep the core engine independent from Home Assistant APIs.
- Keep room configuration in HA config entries, not hardcoded in Python.
- Keep the UI as the primary configuration path.
- Keep the logic bidirectional: summer and winter must both work.
- Keep anti-spam behavior central to the design.
- Keep the backlog only in GitHub issues; do not duplicate it in the repo.
