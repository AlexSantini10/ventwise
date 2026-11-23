"""Command line evaluator for deterministic VentWise scenarios."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .serialization.json_codec import evaluate_scenario


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate a VentWise scenario as deterministic JSON.")
    parser.add_argument("scenario", nargs="?", help="JSON file; stdin when omitted")
    args = parser.parse_args(argv)
    try:
        if args.scenario:
            with open(args.scenario, encoding="utf-8") as handle:
                payload: Any = json.load(handle)
        else:
            payload = json.load(sys.stdin)
        result = evaluate_scenario(payload)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
