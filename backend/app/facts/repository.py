from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from .models import FinancialFact, MoneyAmount


SCHEMA = """
CREATE TABLE IF NOT EXISTS financial_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_end TEXT NOT NULL,
    metric TEXT NOT NULL,
    value_minor_units INTEGER,
    currency TEXT NOT NULL DEFAULT 'GBP',
    unit TEXT NOT NULL,
    reported_or_computed TEXT NOT NULL CHECK (reported_or_computed IN ('reported', 'computed', 'unknown')),
    formula TEXT,
    source_document_id TEXT NOT NULL,
    source_page INTEGER,
    source_quote TEXT NOT NULL,
    extraction_confidence TEXT NOT NULL,
    reviewed INTEGER NOT NULL CHECK (reviewed IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(period_end, metric, reported_or_computed, source_document_id)
);

CREATE INDEX IF NOT EXISTS idx_financial_facts_metric_period
ON financial_facts(metric, period_end);
"""


class FinancialFactsRepository:
    def __init__(self, database_path: str | Path | sqlite3.Connection = ":memory:") -> None:
        if isinstance(database_path, sqlite3.Connection):
            self.connection = database_path
        else:
            self.connection = sqlite3.connect(str(database_path))
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)

    def add_fact(self, fact: FinancialFact) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO financial_facts (
                period_end, metric, value_minor_units, currency, unit,
                reported_or_computed, formula, source_document_id, source_page,
                source_quote, extraction_confidence, reviewed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fact.period_end,
                fact.metric,
                fact.value.minor_units if fact.value else None,
                fact.value.currency if fact.value else "GBP",
                fact.unit,
                fact.reported_or_computed,
                fact.formula,
                fact.source_document_id,
                fact.source_page,
                fact.source_quote,
                str(fact.extraction_confidence),
                1 if fact.reviewed else 0,
            ),
        )
        self.connection.commit()

    def add_facts(self, facts: Iterable[FinancialFact]) -> None:
        for fact in facts:
            self.add_fact(fact)

    def latest_period_end(self) -> str | None:
        row = self.connection.execute("SELECT MAX(period_end) AS period_end FROM financial_facts").fetchone()
        return row["period_end"] if row and row["period_end"] else None

    def get_fact(self, metric: str, period_end: str) -> FinancialFact | None:
        row = self.connection.execute(
            """
            SELECT * FROM financial_facts
            WHERE metric = ? AND period_end = ?
            ORDER BY
                CASE reported_or_computed WHEN 'reported' THEN 0 WHEN 'computed' THEN 1 ELSE 2 END,
                reviewed DESC,
                id DESC
            LIMIT 1
            """,
            (metric, period_end),
        ).fetchone()
        return _row_to_fact(row) if row else None

    def facts_for_period(self, period_end: str) -> list[FinancialFact]:
        rows = self.connection.execute(
            """
            SELECT * FROM financial_facts
            WHERE period_end = ?
            ORDER BY metric ASC
            """,
            (period_end,),
        ).fetchall()
        return [_row_to_fact(row) for row in rows]


def _row_to_fact(row: sqlite3.Row) -> FinancialFact:
    value = None
    if row["value_minor_units"] is not None:
        value = MoneyAmount(minor_units=int(row["value_minor_units"]), currency=row["currency"])
    return FinancialFact(
        period_end=row["period_end"],
        metric=row["metric"],
        value=value,
        unit=row["unit"],
        reported_or_computed=row["reported_or_computed"],
        formula=row["formula"],
        source_document_id=row["source_document_id"],
        source_page=row["source_page"],
        source_quote=row["source_quote"],
        extraction_confidence=Decimal(row["extraction_confidence"]),
        reviewed=bool(row["reviewed"]),
    )
