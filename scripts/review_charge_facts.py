#!/usr/bin/env python3
"""Promote manually reviewed charge fields for exact-answer use.

This script never reviews an entire charge instrument automatically. It either
lists unreviewed candidate fields or applies explicit field-level approvals.

Review decision file shape:
{
  "approved": [
    {
      "chargeCode": "060553930006",
      "field": "description",
      "sourceId": "ch-charge-0006",
      "sourcePage": 3
    }
  ]
}
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FACTS = ROOT / "backend" / "data" / "charge_facts.json"
LEGAL_FIELDS = {
    "description",
    "shortParticulars",
    "securedAssets",
    "securityType",
    "obligationsSecured",
    "instrumentSummary",
}
APPROVABLE_FIELDS = {
    "chargeCode",
    "shortCode",
    "createdDate",
    "deliveredDate",
    "status",
    "satisfiedDate",
    "holder",
    *LEGAL_FIELDS,
}


def load_facts(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    facts = payload.get("facts", payload) if isinstance(payload, dict) else payload
    if not isinstance(facts, list):
        raise SystemExit("Charge facts file must contain a list or {'facts': [...]} payload")
    return facts


def list_pending(facts: list[dict[str, Any]]) -> None:
    pending: list[tuple[dict[str, Any], str]] = []
    for fact in facts:
        field_review = fact.get("fieldReview", {})
        for field in sorted(APPROVABLE_FIELDS):
            if has_value(fact.get(field)) and not field_review.get(field, False):
                pending.append((fact, field))
    if not pending:
        print("No pending extracted charge field candidates with values.")
        return
    for index, (fact, field) in enumerate(pending, start=1):
        evidence = (fact.get("fieldEvidence") or {}).get(field) or {}
        page = evidence.get("sourcePage", fact.get("sourcePage"))
        print(
            f"{index}. charge={fact.get('chargeCode')} field={field} value={fact.get(field)!r} "
            f"source={evidence.get('sourceId', fact.get('sourceId'))} page={page if page is not None else 'missing-page'}"
        )
        quote = evidence.get("sourceQuote") or fact.get("sourceQuote")
        if quote:
            print(f"   quote: {quote}")


def has_value(value: Any) -> bool:
    return value not in (None, "", [])


def apply_decisions(facts: list[dict[str, Any]], decisions_path: Path) -> int:
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    promoted = 0
    for decision in decisions.get("approved", []):
        fact = find_fact(facts, str(decision.get("chargeCode", "")))
        field = str(decision.get("field", ""))
        if field not in APPROVABLE_FIELDS:
            raise SystemExit(f"Unsupported charge field approval: {field}")
        if not has_value(fact.get(field)):
            raise SystemExit(f"Cannot approve empty field {field} for charge {fact.get('chargeCode')}")

        source_id = decision.get("sourceId") or fact.get("sourceId")
        if source_id != fact.get("sourceId"):
            raise SystemExit(f"Approval sourceId {source_id!r} does not match fact sourceId {fact.get('sourceId')!r}")

        page = decision.get("sourcePage")
        field_evidence = fact.setdefault("fieldEvidence", {}).setdefault(field, {})
        if page is None:
            page = field_evidence.get("sourcePage", fact.get("sourcePage"))
        quote = decision.get("sourceQuote") or field_evidence.get("sourceQuote") or fact.get("sourceQuote")
        if page is None or not quote:
            raise SystemExit(f"Cannot approve {field} for charge {fact.get('chargeCode')} without sourcePage and sourceQuote")

        fact["reviewed"] = True
        fact.setdefault("fieldReview", {})[field] = True
        fact["sourcePage"] = page
        fact["sourceQuote"] = quote
        field_evidence.update({"sourceId": source_id, "sourcePage": page, "sourceQuote": quote, "reviewed": True})
        promoted += 1
    return promoted


def find_fact(facts: list[dict[str, Any]], charge_code: str) -> dict[str, Any]:
    normalized = normalize_charge_code(charge_code)
    for fact in facts:
        aliases = {fact.get("chargeCode"), fact.get("displayChargeCode"), fact.get("shortCode")}
        if normalized in {normalize_charge_code(str(alias)) for alias in aliases if alias}:
            return fact
    raise SystemExit(f"No charge fact found for approval chargeCode={charge_code!r}")


def normalize_charge_code(value: str) -> str:
    return "".join(char for char in value if char.isalnum()).lower()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("decisions", type=Path, nargs="?", help="JSON file containing approved charge field keys")
    parser.add_argument("--facts", type=Path, default=DEFAULT_FACTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_FACTS)
    parser.add_argument("--list-pending", action="store_true", help="Print candidate charge fields requiring manual review and exit.")
    args = parser.parse_args()

    facts = load_facts(args.facts)
    if args.list_pending:
        list_pending(facts)
        return
    if args.decisions is None:
        raise SystemExit("Provide a decisions JSON file, or use --list-pending to inspect candidates.")

    promoted = apply_decisions(facts, args.decisions)
    args.output.write_text(json.dumps({"facts": facts}, indent=2) + "\n", encoding="utf-8")
    print(f"Promoted {promoted} reviewed charge fields for exact answers")


if __name__ == "__main__":
    main()
