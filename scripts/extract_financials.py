#!/usr/bin/env python3
"""Load reviewed financial facts into SQLite.

Input CSV columns:
period_end,metric,value_major_units,currency,reported_or_computed,formula,
source_document_id,source_page,source_quote,extraction_confidence,reviewed
"""

from __future__ import annotations

import argparse
import csv
from decimal import Decimal
from pathlib import Path

from backend.app.facts.models import FinancialFact, MoneyAmount
from backend.app.facts.repository import FinancialFactsRepository


def load_csv(csv_path: Path, database_path: Path) -> int:
    repository = FinancialFactsRepository(database_path)
    count = 0
    with csv_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            value = None
            if row.get("value_major_units"):
                value = MoneyAmount.from_major_units(row["value_major_units"], row.get("currency") or "GBP")
            source_page = int(row["source_page"]) if row.get("source_page") else None
            fact = FinancialFact(
                period_end=row["period_end"],
                metric=row["metric"],
                value=value,
                unit="minor_units",
                reported_or_computed=row["reported_or_computed"],
                formula=row.get("formula") or None,
                source_document_id=row["source_document_id"],
                source_page=source_page,
                source_quote=row["source_quote"],
                extraction_confidence=Decimal(row["extraction_confidence"]),
                reviewed=row.get("reviewed", "").lower() in {"1", "true", "yes"},
            )
            repository.add_fact(fact)
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--database", type=Path, default=Path("backend/app.db"))
    args = parser.parse_args()
    count = load_csv(args.csv_path, args.database)
    print(f"Loaded {count} financial facts into {args.database}")


if __name__ == "__main__":
    main()
