from __future__ import annotations

import json
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from .models import FinancialFact, MoneyAmount


SCHEMA = """
CREATE TABLE IF NOT EXISTS financial_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL DEFAULT 'gails-limited',
    period_end TEXT NOT NULL,
    metric TEXT NOT NULL,
    value_minor_units INTEGER,
    currency TEXT NOT NULL DEFAULT 'GBP',
    unit TEXT NOT NULL,
    reported_or_computed TEXT NOT NULL CHECK (reported_or_computed IN ('reported', 'computed', 'unknown', 'unavailable')),
    formula TEXT,
    source_document_id TEXT NOT NULL,
    source_page INTEGER,
    source_quote TEXT NOT NULL,
    extraction_confidence TEXT NOT NULL,
    reviewed INTEGER NOT NULL CHECK (reviewed IN (0, 1)),
    used_in_answers INTEGER NOT NULL DEFAULT 0 CHECK (used_in_answers IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(workspace_id, period_end, metric, reported_or_computed, source_document_id)
);

"""


class FinancialFactsRepository:
    def __init__(self, database_path: str | Path | sqlite3.Connection = ":memory:") -> None:
        if isinstance(database_path, sqlite3.Connection):
            self.connection = database_path
        else:
            self.connection = sqlite3.connect(str(database_path))
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        _ensure_workspace_column(self.connection)
        _ensure_used_in_answers_column(self.connection)
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_financial_facts_metric_period "
            "ON financial_facts(workspace_id, metric, period_end)"
        )
        self.connection.commit()

    def add_fact(self, fact: FinancialFact) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO financial_facts (
                workspace_id, period_end, metric, value_minor_units, currency, unit,
                reported_or_computed, formula, source_document_id, source_page,
                source_quote, extraction_confidence, reviewed, used_in_answers
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fact.workspace_id,
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
                1 if fact.used_in_answers else 0,
            ),
        )
        self.connection.commit()

    def add_facts(self, facts: Iterable[FinancialFact]) -> None:
        for fact in facts:
            self.add_fact(fact)

    def latest_period_end(self, workspace_id: str = "gails-limited", *, usable_only: bool = False) -> str | None:
        where = "workspace_id = ?"
        if usable_only:
            where += " AND reviewed = 1 AND used_in_answers = 1"
        row = self.connection.execute(f"SELECT MAX(period_end) AS period_end FROM financial_facts WHERE {where}", (workspace_id,)).fetchone()
        return row["period_end"] if row and row["period_end"] else None

    def get_fact(self, metric: str, period_end: str, workspace_id: str = "gails-limited", *, usable_only: bool = False) -> FinancialFact | None:
        usable_clause = " AND reviewed = 1 AND used_in_answers = 1" if usable_only else ""
        row = self.connection.execute(
            f"""
            SELECT * FROM financial_facts
            WHERE workspace_id = ? AND metric = ? AND period_end = ?{usable_clause}
            ORDER BY
                CASE reported_or_computed WHEN 'reported' THEN 0 WHEN 'computed' THEN 1 ELSE 2 END,
                reviewed DESC,
                id DESC
            LIMIT 1
            """,
            (workspace_id, metric, period_end),
        ).fetchone()
        return _row_to_fact(row) if row else None

    def facts_for_period(self, period_end: str, workspace_id: str = "gails-limited", *, usable_only: bool = False) -> list[FinancialFact]:
        usable_clause = " AND reviewed = 1 AND used_in_answers = 1" if usable_only else ""
        rows = self.connection.execute(
            f"""
            SELECT * FROM financial_facts
            WHERE workspace_id = ? AND period_end = ?{usable_clause}
            ORDER BY metric ASC
            """,
            (workspace_id, period_end),
        ).fetchall()
        return [_row_to_fact(row) for row in rows]


def _row_to_fact(row: sqlite3.Row) -> FinancialFact:
    value = None
    if row["value_minor_units"] is not None:
        value = MoneyAmount(minor_units=int(row["value_minor_units"]), currency=row["currency"])
    return FinancialFact(
        workspace_id=row["workspace_id"],
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
        used_in_answers=bool(row["used_in_answers"]),
    )


def load_financial_facts_json(path: str | Path) -> list[FinancialFact]:
    """Load structured financial facts from the required JSON facts file shape."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    records = payload.get("facts", payload) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError("financial facts JSON must be a list or an object with a facts list")
    return [_record_to_fact(record) for record in records]



def _record_to_fact(record: dict) -> FinancialFact:
    value = record.get("value")
    currency = record.get("currency", "GBP")
    reported_or_computed = record["reportedOrComputed"]
    return FinancialFact(
        workspace_id=record["workspaceId"],
        period_end=record["periodEnd"],
        metric=str(record["metric"]).lower(),
        value=MoneyAmount.from_major_units(value, currency) if value is not None else None,
        unit=record.get("unit", currency),
        reported_or_computed=reported_or_computed,
        formula=record.get("formula"),
        source_document_id=record["sourceId"],
        source_page=record.get("page"),
        source_quote=record["quote"],
        extraction_confidence=Decimal(str(record.get("extractionConfidence", "1"))),
        reviewed=bool(record.get("reviewed", False)),
        used_in_answers=bool(record.get("usedInAnswers", False)),
    )


def _normalize_reported_or_computed(value: object) -> str:
    normalized = str(value).lower()
    return "unknown" if normalized == "unavailable" else normalized


def _ensure_workspace_column(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(financial_facts)")}
    if "workspace_id" not in columns:
        connection.execute("ALTER TABLE financial_facts ADD COLUMN workspace_id TEXT NOT NULL DEFAULT 'gails-limited'")
        connection.commit()


def _ensure_used_in_answers_column(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(financial_facts)")}
    if "used_in_answers" not in columns:
        connection.execute("ALTER TABLE financial_facts ADD COLUMN used_in_answers INTEGER NOT NULL DEFAULT 0 CHECK (used_in_answers IN (0, 1))")
        connection.commit()
