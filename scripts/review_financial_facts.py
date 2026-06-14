#!/usr/bin/env python3
"""Promote manually reviewed financial facts for exact-answer use.

This script does not review facts itself. It applies reviewer decisions from a
small JSON file so promotion is explicit and auditable.

Review decision file shape:
{
  "approved": [
    {"workspaceId":"gails-limited", "periodEnd":"2025-02-28", "metric":"revenue", "sourceId":"ch-parent-accounts-2025"}
  ]
}
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FACTS = ROOT / "backend" / "data" / "financial_facts.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("decisions", type=Path, help="JSON file containing approved fact keys")
    parser.add_argument("--facts", type=Path, default=DEFAULT_FACTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_FACTS)
    args = parser.parse_args()

    payload = json.loads(args.facts.read_text(encoding="utf-8"))
    facts = payload.get("facts", payload)
    decisions = json.loads(args.decisions.read_text(encoding="utf-8"))
    approved = {key(item) for item in decisions.get("approved", [])}

    promoted = 0
    for fact in facts:
        if key(fact) in approved:
            if fact.get("value") in (None, ""):
                raise SystemExit(f"Cannot approve fact without value: {key(fact)}")
            if not fact.get("quote") or fact.get("page") is None:
                raise SystemExit(f"Cannot approve fact without page and quote: {key(fact)}")
            fact["reviewed"] = True
            fact["usedInAnswers"] = True
            promoted += 1
        else:
            fact["usedInAnswers"] = False if not fact.get("reviewed") else bool(fact.get("usedInAnswers", False))

    args.output.write_text(json.dumps({"facts": facts}, indent=2) + "\n", encoding="utf-8")
    print(f"Promoted {promoted} reviewed financial facts for exact answers")


def key(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(item.get("workspaceId", "gails-limited")),
        str(item.get("periodEnd")),
        str(item.get("metric")).lower(),
        str(item.get("sourceId")),
    )


if __name__ == "__main__":
    main()
