# Project Overview

## Problem Statement

The project decides whether opening or closing windows is likely to improve
indoor comfort.

The recommender should:

- work with more than one room
- account for indoor and outdoor comfort
- avoid noisy or trivial notifications
- stay simple to configure from Home Assistant

## Target Rooms

Initial room groups:

- Camera
- Zona giorno

The project must remain generic enough to support more rooms later.

## Final Product Shape

The final deliverable is a Home Assistant custom integration that:

- is installable via HACS
- exposes a device and entities in Home Assistant
- supports UI-based configuration
- uses a reusable Python scoring core

## Non-Goals

- It is not a direct window actuator.
- It does not physically open or close windows.
- It does not rely on manual YAML edits for normal use.

