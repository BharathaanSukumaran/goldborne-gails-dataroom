from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS documents (
  document_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  category TEXT NOT NULL,
  source TEXT NOT NULL,
  source_url TEXT NOT NULL,
  document_date TEXT NOT NULL,
  reporting_period_end TEXT,
  inbox_file TEXT,
  processed_path TEXT,
  copyright_policy TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS companies (
  company_number TEXT PRIMARY KEY,
  legal_name TEXT NOT NULL,
  status TEXT,
  registered_office TEXT,
  sic_codes TEXT
);

CREATE TABLE IF NOT EXISTS financial_facts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  metric TEXT NOT NULL,
  value REAL,
  unit TEXT NOT NULL,
  period_end TEXT NOT NULL,
  source_document_id TEXT NOT NULL,
  page INTEGER,
  confidence TEXT NOT NULL,
  note TEXT,
  FOREIGN KEY(source_document_id) REFERENCES documents(document_id)
);

CREATE TABLE IF NOT EXISTS charges (
  charge_code TEXT PRIMARY KEY,
  created_date TEXT NOT NULL,
  status TEXT NOT NULL,
  holder TEXT NOT NULL,
  source_document_id TEXT NOT NULL,
  FOREIGN KEY(source_document_id) REFERENCES documents(document_id)
);

CREATE TABLE IF NOT EXISTS officers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  role TEXT NOT NULL,
  appointed_date TEXT,
  resigned_date TEXT,
  status TEXT NOT NULL,
  source_document_id TEXT NOT NULL,
  FOREIGN KEY(source_document_id) REFERENCES documents(document_id)
);

CREATE TABLE IF NOT EXISTS ownership (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_name TEXT NOT NULL,
  control_type TEXT NOT NULL,
  percentage_band TEXT,
  status TEXT NOT NULL,
  source_document_id TEXT NOT NULL,
  FOREIGN KEY(source_document_id) REFERENCES documents(document_id)
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_date TEXT NOT NULL,
  event_type TEXT NOT NULL,
  summary TEXT NOT NULL,
  risk_relevance TEXT,
  source_document_id TEXT NOT NULL,
  FOREIGN KEY(source_document_id) REFERENCES documents(document_id)
);

CREATE TABLE IF NOT EXISTS qa_findings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  severity TEXT NOT NULL,
  finding TEXT NOT NULL,
  status TEXT NOT NULL,
  document_id TEXT
);
"""


TABLES = [
    "financial_facts",
    "charges",
    "officers",
    "ownership",
    "events",
    "qa_findings",
    "companies",
    "documents",
]


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def reset(conn: sqlite3.Connection) -> None:
    for table in TABLES:
        conn.execute(f"DELETE FROM {table}")
    conn.commit()


def insert_document(conn: sqlite3.Connection, doc: dict[str, Any], processed_path: str | None) -> None:
    conn.execute(
        """
        INSERT INTO documents (
          document_id, title, category, source, source_url, document_date,
          reporting_period_end, inbox_file, processed_path, copyright_policy
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            doc["document_id"],
            doc["title"],
            doc["category"],
            doc["source"],
            doc["source_url"],
            doc["date"],
            doc.get("reporting_period_end"),
            doc.get("expected_inbox_file"),
            processed_path,
            doc["copyright_policy"],
        ),
    )


def insert_seed(conn: sqlite3.Connection, seed: dict[str, Any]) -> None:
    company = seed["company"]
    conn.execute(
        """
        INSERT INTO companies (company_number, legal_name, status, registered_office, sic_codes)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            company["company_number"],
            company["legal_name"],
            company.get("status"),
            company.get("registered_office"),
            ", ".join(company.get("sic_codes", [])),
        ),
    )

    for fact in seed.get("financial_facts", []):
        conn.execute(
            """
            INSERT INTO financial_facts
              (metric, value, unit, period_end, source_document_id, page, confidence, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fact["metric"],
                fact.get("value"),
                fact["unit"],
                fact["period_end"],
                fact["source_document_id"],
                fact.get("page"),
                fact["confidence"],
                fact.get("note"),
            ),
        )

    for charge in seed.get("charges", []):
        conn.execute(
            """
            INSERT INTO charges (charge_code, created_date, status, holder, source_document_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                charge["charge_code"],
                charge["created_date"],
                charge["status"],
                charge["holder"],
                charge["source_document_id"],
            ),
        )

    for officer in seed.get("officers", []):
        conn.execute(
            """
            INSERT INTO officers
              (name, role, appointed_date, resigned_date, status, source_document_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                officer["name"],
                officer["role"],
                officer.get("appointed_date"),
                officer.get("resigned_date"),
                officer["status"],
                officer["source_document_id"],
            ),
        )

    for owner in seed.get("ownership", []):
        conn.execute(
            """
            INSERT INTO ownership
              (owner_name, control_type, percentage_band, status, source_document_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                owner["owner_name"],
                owner["control_type"],
                owner.get("percentage_band"),
                owner["status"],
                owner["source_document_id"],
            ),
        )

    for event in seed.get("events", []):
        conn.execute(
            """
            INSERT INTO events
              (event_date, event_type, summary, risk_relevance, source_document_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event["event_date"],
                event["event_type"],
                event["summary"],
                event.get("risk_relevance"),
                event["source_document_id"],
            ),
        )
    conn.commit()


def rows(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(query, params).fetchall()]
