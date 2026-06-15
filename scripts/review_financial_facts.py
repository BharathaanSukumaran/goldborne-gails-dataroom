#!/usr/bin/env python3
"""Promote manually reviewed financial facts for exact-answer use.

This script does not review facts itself. It either lists pending candidate facts
or applies reviewer decisions from a small JSON file so promotion is explicit
and auditable.

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


def load_facts(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    facts = payload.get("facts", payload)
    if not isinstance(facts, list):
        raise SystemExit("Financial facts file must contain a list or {'facts': [...]} payload")
    return facts


def list_pending(facts: list[dict[str, Any]]) -> None:
    candidates = [fact for fact in facts if fact.get("value") not in {None, ""} and not fact.get("usedInAnswers")]
    if not candidates:
        print("No pending extracted financial fact candidates with values.")
        return
    for index, fact in enumerate(candidates, start=1):
        page = fact.get("page") if fact.get("page") is not None else "missing-page"
        print(
            f"{index}. {fact.get('periodEnd')} {fact.get('metric')}={fact.get('value')} "
            f"source={fact.get('sourceId')} page={page} reviewed={fact.get('reviewed')} usedInAnswers={fact.get('usedInAnswers')}"
        )
        print(f"   quote: {fact.get('quote')}")


def apply_decisions(facts: list[dict[str, Any]], decisions_path: Path) -> int:
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
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
        elif not fact.get("reviewed"):
            fact["usedInAnswers"] = False
    return promoted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("decisions", type=Path, nargs="?", help="JSON file containing approved fact keys")
    parser.add_argument("--facts", type=Path, default=DEFAULT_FACTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_FACTS)
    parser.add_argument("--list-pending", action="store_true", help="Print candidate facts requiring manual review and exit.")
    args = parser.parse_args()

    facts = load_facts(args.facts)
    if args.list_pending:
        list_pending(facts)
        return
    if args.decisions is None:
        raise SystemExit("Provide a decisions JSON file, or use --list-pending to inspect candidates.")

    promoted = apply_decisions(facts, args.decisions)
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
