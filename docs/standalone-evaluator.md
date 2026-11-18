# Standalone engine evaluator

`ventwise_core` is the canonical, dependency-free VentWise decision package.
Home Assistant imports it through a compatibility wrapper, while local tools
can evaluate the same engine without Docker, Home Assistant, a database, or an
HA profile.

## Input

The evaluator accepts a JSON object with:

- `evaluated_at`: ISO-8601 timestamp;
- `config`: fields from `DecisionConfig`;
- `context`: quiet-hours, cooldown, and stability state;
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
`normalized_input`, and the complete `core_result`. Localized presentation
strings are not part of the comparison contract.

Home Assistant diagnostics expose the same normalized snapshot and core
result, together with `delivered_result` and explicit delivery
transformations. This makes window-state gating, action guardrails, quiet
hours, cooldown, and notification delivery visible without changing the pure
core result.
