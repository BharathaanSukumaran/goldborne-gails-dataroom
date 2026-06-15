#!/usr/bin/env python3
"""Extract candidate financial facts from processed Companies House account text.

The extractor is intentionally conservative. It can identify simple line-item
patterns in text extracted from Companies House accounts, but every output fact
is written with reviewed=false and usedInAnswers=false. A human reviewer must
confirm page/source evidence before exact answers can use the value.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.facts.models import FinancialFact, MoneyAmount
from backend.app.facts.repository import FinancialFactsRepository

DEFAULT_OUTPUT = ROOT / "backend" / "data" / "financial_facts.json"
TEXT_DIR = ROOT / "dataroom" / "processed" / "accounts_text"

ACCOUNT_SOURCES = [
    ("ch-parent-accounts-2025", "2025-02-28", TEXT_DIR / "ch-parent-accounts-2025.txt"),
    ("ch-parent-accounts-2024", "2024-02-29", TEXT_DIR / "ch-parent-accounts-2024.txt"),
    ("ch-parent-accounts-2023", "2023-02-28", TEXT_DIR / "ch-parent-accounts-2023.txt"),
]

METRIC_PATTERNS: dict[str, list[str]] = {
    "revenue": [r"\brevenue\b", r"\bturnover\b"],
    "turnover": [r"\bturnover\b"],
    "operating_profit": [r"\boperating profit\b"],
    "profit_before_tax": [r"\bprofit before tax\b", r"\bprofit on ordinary activities before taxation\b"],
    "profit_after_tax": [r"\bprofit for the financial year\b", r"\bprofit after tax\b", r"\bprofit for the year\b"],
    "cash": [r"\bcash at bank and in hand\b", r"\bcash and cash equivalents\b"],
    "borrowings": [r"\bborrowings\b", r"\bbank loans\b"],
    "debt": [r"\bnet debt\b", r"\btotal debt\b", r"\bborrowings\b"],
    "net_assets": [r"\bnet assets\b"],
    "depreciation": [r"\bdepreciation\b"],
    "amortisation": [r"\bamortisation\b", r"\bamortization\b"],
}

REQUIRED_METRICS = [
    "revenue",
    "turnover",
    "ebitda",
    "operating_profit",
    "profit_before_tax",
    "profit_after_tax",
    "cash",
    "borrowings",
    "debt",
    "net_assets",
    "depreciation",
    "amortisation",
]

MONEY_RE = re.compile(r"(?<![A-Za-z])(?:£\s*)?\(?(-?\d{1,3}(?:,\d{3})+|-?\d+)\)?")
TRUTHY = {"1", "true", "yes", "y"}
UNAVAILABLE_STATUSES = {"", "unknown", "unavailable", "not_available", "not available"}


@dataclass(frozen=True)
class Candidate:
    metric: str
    value: str | None
    quote: str
    page: int | None
    confidence: str



def load_csv(csv_path: Path, database_path: Path) -> int:
    repository = FinancialFactsRepository(database_path)
    facts = [record_to_financial_fact(record) for record in read_csv_records(csv_path)]
    repository.add_facts(facts)
    return len(facts)


def read_csv_records(csv_path: Path) -> list[dict[str, Any]]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return [csv_row_to_json_fact(row) for row in csv.DictReader(handle)]


def csv_row_to_json_fact(row: dict[str, str | None]) -> dict[str, Any]:
    metric = required(row, "metric").lower()
    if metric not in set(REQUIRED_METRICS):
        raise ValueError(f"Unsupported financial metric: {metric}")

    value = optional(row, "value", "value_major_units")
    if value == "":
        value = None
    if value is not None:
        value = decimal_string(value)

    reported = optional(row, "reportedOrComputed", "reported_or_computed") or "unavailable"
    reported = reported.lower()
    if reported in UNAVAILABLE_STATUSES:
        reported = "unavailable"
    if reported not in {"reported", "computed", "unavailable"}:
        raise ValueError(f"Invalid reportedOrComputed value: {reported}")

    page = optional(row, "page", "source_page")
    source_id = required(row, "sourceId", "source_document_id")
    quote = required(row, "quote", "source_quote")
    reviewed_requested = parse_bool(optional(row, "reviewed"))
    used_requested = parse_bool(optional(row, "usedInAnswers", "used_in_answers"))
    has_evidence = has_source_evidence(source_id, page, quote)
    reviewed = reviewed_requested and has_evidence
    used_in_answers = used_requested and reviewed

    return {
        "workspaceId": optional(row, "workspaceId", "workspace_id") or "gails-limited",
        "metric": metric,
        "periodEnd": required(row, "periodEnd", "period_end"),
        "value": value,
        "currency": optional(row, "currency") or "GBP",
        "unit": optional(row, "unit") or "GBP",
        "reportedOrComputed": reported,
        "formula": optional(row, "formula") or None,
        "sourceId": source_id,
        "page": int(page) if page not in {None, ""} else None,
        "quote": quote,
        "extractionConfidence": decimal_string(optional(row, "extractionConfidence", "extraction_confidence") or "1"),
        "reviewed": reviewed,
        "usedInAnswers": used_in_answers,
    }


def record_to_financial_fact(record: dict[str, Any]) -> FinancialFact:
    value = record.get("value")
    currency = record.get("currency", "GBP")
    reported = record["reportedOrComputed"]
    return FinancialFact(
        workspace_id=record.get("workspaceId", "gails-limited"),
        period_end=record["periodEnd"],
        metric=record["metric"],
        value=MoneyAmount.from_major_units(value, currency) if value is not None else None,
        unit="minor_units",
        reported_or_computed=reported,
        formula=record.get("formula"),
        source_document_id=record["sourceId"],
        source_page=record.get("page"),
        source_quote=record["quote"],
        extraction_confidence=Decimal(str(record.get("extractionConfidence", "1"))),
        reviewed=bool(record.get("reviewed", False)),
        used_in_answers=bool(record.get("usedInAnswers", False)),
    )


def write_facts_json(records: Iterable[dict[str, Any]], output_path: Path) -> int:
    payload = {"facts": list(records)}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return len(payload["facts"])


def required(row: dict[str, str | None], *names: str) -> str:
    value = optional(row, *names)
    if value in {None, ""}:
        raise ValueError(f"Missing required column: {'/'.join(names)}")
    return value


def optional(row: dict[str, str | None], *names: str) -> str | None:
    for name in names:
        value = row.get(name)
        if value is not None:
            return value.strip()
    return None


def parse_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in TRUTHY


def decimal_string(value: str | int | Decimal) -> str:
    try:
        decimal_value = Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid decimal value: {value!r}") from exc
    return format(decimal_value, "f")


def has_source_evidence(source_id: str, page: int | str | None, quote: str | None) -> bool:
    return bool(source_id and page not in {None, ""} and quote and quote.strip())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    facts: list[dict[str, Any]] = []
    for source_id, period_end, text_path in ACCOUNT_SOURCES:
        text = text_path.read_text(encoding="utf-8", errors="ignore") if text_path.exists() else ""
        candidates = extract_candidates(text)
        by_metric = {candidate.metric: candidate for candidate in candidates}
        for metric in REQUIRED_METRICS:
            candidate = by_metric.get(metric)
            facts.append(to_fact(source_id, period_end, metric, candidate))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"facts": facts}, indent=2) + "\n", encoding="utf-8")
    extracted = sum(1 for fact in facts if fact["value"] is not None)
    print(f"Wrote {len(facts)} financial fact records to {args.output}")
    print(f"Extracted candidate values: {extracted}")
    print("Reviewed usable facts: 0. Parser output is never auto-approved; use review_financial_facts.py after human review.")


def extract_candidates(text: str) -> list[Candidate]:
    if not meaningful_text(text):
        return []
    out: list[Candidate] = []
    pages = text.split("\f") if "\f" in text else [text]
    for metric, patterns in METRIC_PATTERNS.items():
        for page_number, page_text in enumerate(pages, start=1):
            lines = [line.strip() for line in page_text.splitlines() if line.strip()]
            for line in lines:
                normalized = re.sub(r"\s+", " ", line).strip()
                if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in patterns):
                    value = extract_first_money(normalized)
                    if value is not None:
                        out.append(Candidate(metric=metric, value=value, quote=normalized[:260], page=page_number, confidence="0.4"))
                        break
            if any(candidate.metric == metric for candidate in out):
                break
    return out


def meaningful_text(text: str) -> bool:
    alnum = sum(1 for char in text if char.isalnum())
    return alnum > 200


def extract_first_money(line: str) -> str | None:
    matches = MONEY_RE.findall(line)
    if not matches:
        return None
    cleaned = matches[-1].replace(",", "")
    return cleaned


def to_fact(source_id: str, period_end: str, metric: str, candidate: Candidate | None) -> dict[str, Any]:
    if metric == "ebitda" and candidate is None:
        quote = "EBITDA was not directly extracted. It may only be computed after operating profit, depreciation, and amortisation are reviewed and usable."
    elif candidate is None:
        quote = f"{metric} is unavailable from current extracted text and requires OCR/manual review of the Companies House accounts."
    else:
        quote = candidate.quote
    return {
        "workspaceId": "gails-limited",
        "metric": metric,
        "periodEnd": period_end,
        "value": candidate.value if candidate else None,
        "currency": "GBP",
        "unit": "GBP",
        "reportedOrComputed": "reported" if candidate else "unavailable",
        "formula": None,
        "sourceId": source_id,
        "page": candidate.page if candidate else None,
        "quote": quote,
        "extractionConfidence": candidate.confidence if candidate else "0",
        "reviewed": False,
        "usedInAnswers": False,
    }


if __name__ == "__main__":
    main()
