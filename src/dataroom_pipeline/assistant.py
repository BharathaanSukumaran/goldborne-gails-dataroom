from __future__ import annotations

import sqlite3
from typing import Any

from .paths import DB_PATH
from .storage import connect, rows
from .llm_client import synthesize


def answer_question(question: str, db_path=DB_PATH) -> dict[str, Any]:
    q = question.lower().strip()
    conn = connect(db_path)
    try:
        if any(term in q for term in ["revenue", "ebitda", "debt", "financial"]):
            return _financial_answer(conn)
        if "charge" in q or "lender" in q or "security" in q:
            return _charges_answer(conn)
        if "owner" in q or "ownership" in q or "psc" in q or "ultimate" in q:
            return _ownership_answer(conn)
        if "director" in q or "management" in q:
            return _management_answer(conn)
        if "risk" in q or "credit" in q or "summary" in q:
            return _credit_answer(conn)
        return {
            "answer": "The dataroom does not contain enough structured evidence to answer that question reliably.",
            "citations": [],
            "route": "unsupported",
        }
    finally:
        conn.close()


def _financial_answer(conn: sqlite3.Connection) -> dict[str, Any]:
    facts = rows(
        conn,
        """
        SELECT f.metric, f.value, f.unit, f.period_end, f.confidence, f.note,
               d.title, d.source_url
        FROM financial_facts f
        JOIN documents d ON d.document_id = f.source_document_id
        ORDER BY f.period_end DESC, f.metric
        """,
    )
    if not facts:
        return _unsupported()

    unavailable = [fact for fact in facts if fact["value"] is None]
    if unavailable:
        lines = [
            "The pipeline has identified the relevant source accounts, but the exact financial values are not yet populated because the source PDF still needs to be dropped into the dataroom and verified."
        ]
        for fact in unavailable:
            lines.append(f"- {fact['metric']} for {fact['period_end']}: {fact['note']}")
        return {
            "answer": "\n".join(lines),
            "citations": _citations(facts),
            "route": "structured_facts",
        }

    lines = [
        f"{fact['metric']} for {fact['period_end']} was {fact['value']:,.0f} {fact['unit']}."
        for fact in facts
    ]
    return {"answer": "\n".join(lines), "citations": _citations(facts), "route": "structured_facts"}


def _charges_answer(conn: sqlite3.Connection) -> dict[str, Any]:
    charges = rows(
        conn,
        """
        SELECT c.charge_code, c.created_date, c.status, c.holder, d.title, d.source_url
        FROM charges c
        JOIN documents d ON d.document_id = c.source_document_id
        ORDER BY c.created_date DESC
        """,
    )
    if not charges:
        return _unsupported()
    answer = "\n".join(
        f"- {charge['charge_code']}, created {charge['created_date']}, is {charge['status']} and held by {charge['holder']}."
        for charge in charges
    )
    return {"answer": answer, "citations": _citations(charges), "route": "structured_facts"}


def _ownership_answer(conn: sqlite3.Connection) -> dict[str, Any]:
    owners = rows(
        conn,
        """
        SELECT o.owner_name, o.control_type, o.percentage_band, o.status, d.title, d.source_url
        FROM ownership o
        JOIN documents d ON d.document_id = o.source_document_id
        """,
    )
    if not owners:
        return _unsupported()
    answer = "\n".join(
        f"- {owner['owner_name']} is listed as an {owner['status']} {owner['control_type']} with {owner['percentage_band']} control."
        for owner in owners
    )
    return {"answer": answer, "citations": _citations(owners), "route": "structured_facts"}


def _management_answer(conn: sqlite3.Connection) -> dict[str, Any]:
    officers = rows(
        conn,
        """
        SELECT o.name, o.role, o.appointed_date, o.resigned_date, o.status, d.title, d.source_url
        FROM officers o
        JOIN documents d ON d.document_id = o.source_document_id
        ORDER BY o.status, o.name
        """,
    )
    if not officers:
        return _unsupported()
    answer = "\n".join(
        f"- {officer['name']}: {officer['role']}, {officer['status']}."
        for officer in officers
    )
    return {"answer": answer, "citations": _citations(officers), "route": "structured_facts"}


def _credit_answer(conn: sqlite3.Connection) -> dict[str, Any]:
    charges = rows(conn, "SELECT charge_code, holder, status FROM charges ORDER BY created_date DESC")
    owners = rows(conn, "SELECT owner_name, percentage_band FROM ownership")
    events = rows(
        conn,
        """
        SELECT e.summary, e.risk_relevance, d.title, d.source_url
        FROM events e
        JOIN documents d ON d.document_id = e.source_document_id
        ORDER BY e.event_date DESC
        """,
    )
    citations = _citations(events)
    charge_text = "; ".join(f"{c['charge_code']} held by {c['holder']}" for c in charges) or "no registered charges in the normalized dataset"
    owner_text = "; ".join(f"{o['owner_name']} ({o['percentage_band']})" for o in owners) or "ownership not populated"
    risks = [event["risk_relevance"] for event in events if event.get("risk_relevance")]
    deterministic_answer = (
        "Credit summary: Gail's is represented in the dataroom as an active UK bakery/cafe operator with ownership linked to "
        f"{owner_text}. The current normalized charges dataset shows {charge_text}. "
        "Key lender risks from the current dataroom are: "
        + ("; ".join(risks) if risks else "insufficient event evidence has been normalized.")
        + " Exact financial leverage and EBITDA commentary should remain provisional until the source accounts PDFs are added and validated."
    )
    source_context = {
        "ownership": owners,
        "charges": charges,
        "events": events,
        "deterministic_answer": deterministic_answer,
    }
    llm_answer = synthesize(
        "You are a credit dataroom assistant. Use only the supplied structured context. "
        "Do not invent missing financial values. Keep the answer concise and lender-focused.",
        "Draft a credit summary from this context:\n" + str(source_context),
    )
    if llm_answer:
        return {"answer": llm_answer, "citations": citations, "route": "structured_plus_llm_synthesis"}
    return {"answer": deterministic_answer, "citations": citations, "route": "structured_plus_events"}


def _citations(rows_: list[dict[str, Any]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    citations: list[dict[str, str]] = []
    for row in rows_:
        title = str(row.get("title") or "Source document")
        url = str(row.get("source_url") or "")
        key = (title, url)
        if key not in seen:
            citations.append({"title": title, "url": url})
            seen.add(key)
    return citations


def _unsupported() -> dict[str, Any]:
    return {
        "answer": "The dataroom does not contain enough evidence to answer that reliably.",
        "citations": [],
        "route": "unsupported",
    }
