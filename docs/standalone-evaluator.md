# Standalone engine evaluator

`ventwise_core` is the canonical, dependency-free VentWise decision package.
Home Assistant imports it through a compatibility wrapper, while local tools
can evaluate the same engine without Docker, Home Assistant, a database, or an
HA profile.

## Input

The evaluator accepts a JSON object with:

- `evaluated_at`: ISO-8601 timestamp;
- `config`: fields from `DecisionConfig`;
- `context`: persisted per-room guardrail state (delivery settings remain HA-only);
- `rooms`: normalized observations and room targets;
- `outdoor`: normalized outdoor observations and safety configuration.

Every observation contains `value`, `unit`, `observed_at`, and `source_id`.
Optional quality fields are `validity`, `availability`, `freshness_seconds`,
`quality_reason`, and `provenance`.

## CLI

From the repository root:

```powershell
$env:PYTHONPATH = "src"
python -m ventwise_core scenario.json
Get-Content scenario.json | python -m ventwise_core
```

The output is stable JSON containing `schema_version`, `config`,
`normalized_input`, and the complete `core_result`. Schema v2 makes window
state and guardrails explicit core inputs and returns updated guardrail state.
Readers remain compatible with v1 input documents. Localized presentation
strings are not part of the comparison contract.

Home Assistant diagnostics expose the same normalized snapshot and core
result, together with `delivered_result` and explicit delivery
transformations. Recommendation summaries and sensors project `core_result`
directly. Quiet hours, cooldown, channel availability, and stability filter
notifications only. Parity is compared between standalone and Home Assistant
`core_result`, not between core evaluation and notification delivery.
