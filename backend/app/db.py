from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

from .config import DATABASE_URL, MANIFEST_PATH, PROJECT_ROOT

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
  source_id TEXT PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL, issuer TEXT NOT NULL,
  retrieved_at TEXT NOT NULL, source_url TEXT NOT NULL, local_path TEXT NOT NULL,
  included_reason TEXT NOT NULL, processing_status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS financial_facts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, period_end TEXT NOT NULL, metric TEXT NOT NULL,
  value_minor_units INTEGER, currency TEXT NOT NULL DEFAULT 'GBP', unit TEXT NOT NULL DEFAULT 'pence',
  reported_or_computed TEXT NOT NULL, formula TEXT, source_document_id TEXT NOT NULL, source_page INTEGER,
  source_quote TEXT NOT NULL, extraction_confidence TEXT NOT NULL, reviewed INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY(source_document_id) REFERENCES sources(source_id)
);
CREATE TABLE IF NOT EXISTS charges (
  charge_code TEXT PRIMARY KEY, created_date TEXT NOT NULL, status TEXT NOT NULL, holder TEXT NOT NULL,
  source_document_id TEXT NOT NULL, source_page INTEGER, source_quote TEXT NOT NULL,
  FOREIGN KEY(source_document_id) REFERENCES sources(source_id)
);
CREATE TABLE IF NOT EXISTS officers (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, role TEXT NOT NULL, appointed_date TEXT,
  resigned_date TEXT, status TEXT NOT NULL, source_document_id TEXT NOT NULL, source_quote TEXT NOT NULL,
  FOREIGN KEY(source_document_id) REFERENCES sources(source_id)
);
CREATE TABLE IF NOT EXISTS ownership (
  id INTEGER PRIMARY KEY AUTOINCREMENT, owner_name TEXT NOT NULL, control_type TEXT NOT NULL,
  percentage_band TEXT, status TEXT NOT NULL, source_document_id TEXT NOT NULL, source_quote TEXT NOT NULL,
  FOREIGN KEY(source_document_id) REFERENCES sources(source_id)
);
CREATE TABLE IF NOT EXISTS document_chunks (
  chunk_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, page INTEGER, text TEXT NOT NULL,
  FOREIGN KEY(source_id) REFERENCES sources(source_id)
);
"""

def db_path() -> Path:
    parsed = urlparse(DATABASE_URL)
    if parsed.scheme and parsed.scheme != "sqlite":
        raise ValueError("This demo uses SQLite locally; set DATABASE_URL to sqlite:///path")
    if parsed.scheme == "sqlite":
        return Path(parsed.path)
    return Path(DATABASE_URL)

def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn

def rows(query: str, params: tuple = ()) -> list[dict]:
    with connect() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]

def seed_database() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    with connect() as conn:
        for table in ["document_chunks", "financial_facts", "charges", "officers", "ownership", "sources"]:
            conn.execute(f"DELETE FROM {table}")
        for s in manifest["sources"]:
            conn.execute("INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                s["source_id"], s["title"], s["category"], s["issuer"], s["retrieved_at"], s["source_url"],
                s["local_path"], s["included_reason"], s["processing_status"]
            ))
        for metric in ["revenue", "EBITDA", "debt"]:
            conn.execute("""INSERT INTO financial_facts
              (period_end, metric, value_minor_units, currency, unit, reported_or_computed, formula, source_document_id, source_page, source_quote, extraction_confidence, reviewed)
              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
                "2025-02-28", metric, None, "GBP", "pence", "unknown", None, "ch-parent-accounts-2025", None,
                "Financial value unavailable until the source accounts PDF is ingested and human-reviewed.", "pending_source_pdf", 0
            ))
        for charge in [
          ("0605 5393 0006", "2022-06-06", "outstanding", "Glas Trust Corporation Limited", "ch-charge-0006"),
          ("0605 5393 0005", "2021-11-04", "outstanding", "Glas Trust Corporation Limited", "ch-charge-0005"),
        ]:
            conn.execute("INSERT INTO charges VALUES (?, ?, ?, ?, ?, ?, ?)", (*charge, None, "Companies House charges metadata records this charge as outstanding and held by Glas Trust Corporation Limited."))
        for officer in [
          ("Nicholas John Ayerst", "Director", "2025-07-07", None, "current"),
          ("Thomas Ralph Molnar", "Director", None, None, "current"),
          ("Andy Trigwell", "Director", None, None, "current"),
          ("Marta Barbara Pogroszewska", "Director", None, "2025-07-07", "resigned"),
        ]:
            conn.execute("""INSERT INTO officers (name, role, appointed_date, resigned_date, status, source_document_id, source_quote)
              VALUES (?, ?, ?, ?, ?, ?, ?)""", (*officer, "ch-officers-06055393", "Companies House officers metadata."))
        conn.execute("""INSERT INTO ownership (owner_name, control_type, percentage_band, status, source_document_id, source_quote)
          VALUES (?, ?, ?, ?, ?, ?)""", ("Bread Limited", "person with significant control", "75% or more", "active", "ch-psc-06055393", "Companies House PSC metadata."))
        for s in manifest["sources"]:
            lp = PROJECT_ROOT / s["local_path"]
            if lp.exists() and lp.suffix.lower() in {".md", ".txt", ".html"}:
                text = lp.read_text(encoding="utf-8", errors="ignore")
            else:
                text = f"{s['title']}\nCategory: {s['category']}\nReason: {s['included_reason']}\nNotes: {s.get('notes') or ''}"
            conn.execute("INSERT INTO document_chunks VALUES (?, ?, ?, ?)", (s["source_id"] + ":1", s["source_id"], 1, text[:4000]))
        conn.commit()
