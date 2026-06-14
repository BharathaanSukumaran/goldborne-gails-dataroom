from __future__ import annotations

from dataclasses import asdict

from .ebitda import resolve_ebitda
from .models import FinancialFact
from .repository import FinancialFactsRepository


def build_financial_answer(
    question: str,
    repository: FinancialFactsRepository,
    *,
    model_draft: str | None = None,
) -> dict:
    """Build API-ready financial answers from DB facts only.

    The optional model_draft is accepted for API integration tests and future
    wording assistance, but numeric values are deliberately sourced from
    reviewed, answer-usable financial_facts so model approximations and unreviewed values cannot leak into the answer.
    """

    del model_draft
    lower_question = question.lower()
    period_end = repository.latest_period_end(usable_only=True)
    if period_end is None:
        missing = _requested_financial_metrics(lower_question)
        return {
            "answer": "The requested financial metrics are unknown because no reviewed financial facts have been approved for answers.",
            "answer_type": "unknown",
            "facts_used": [],
            "citations": [],
            "missing_information": [*missing, "reviewed usable financial_facts"],
            "confidence": "low",
        }

    value_facts: list[FinancialFact] = []
    facts_used: list[FinancialFact] = []
    parts = [f"For the period ended {period_end}:"]
    missing: list[str] = []

    if "revenue" in lower_question or "turnover" in lower_question:
        revenue = repository.get_fact("revenue", period_end, usable_only=True)
        if revenue and revenue.value:
            value_facts.append(revenue)
            facts_used.append(revenue)
            parts.append(f"revenue was {revenue.value.format()} ({revenue.reported_or_computed}).")
        else:
            missing.append("revenue")

    if "ebitda" in lower_question:
        ebitda = resolve_ebitda(repository, period_end)
        if ebitda.value:
            value_facts.append(ebitda)
            facts_used.append(ebitda)
            suffix = f" using {ebitda.formula}" if ebitda.reported_or_computed == "computed" else ""
            parts.append(f"EBITDA was {ebitda.value.format()} ({ebitda.reported_or_computed}{suffix}).")
        else:
            missing.append("EBITDA")
            parts.append("EBITDA is unavailable because it was not reported and could not be computed from complete reviewed usable components.")

    if "debt" in lower_question or "borrowings" in lower_question:
        debt = repository.get_fact("debt", period_end, usable_only=True)
        if debt and debt.value:
            value_facts.append(debt)
            facts_used.append(debt)
            parts.append(f"debt was {debt.value.format()} ({debt.reported_or_computed}).")
        else:
            missing.append("debt")

    if not value_facts and not missing:
        return {
            "answer": "I cannot answer this financial question from structured financial facts.",
            "answer_type": "unknown",
            "facts_used": [],
            "citations": [],
            "missing_information": ["supported financial metric"],
            "confidence": "low",
        }

    if not value_facts and missing and "reviewed usable financial_facts" not in missing:
        missing.append("reviewed usable financial_facts")

    citations = [_citation(fact) for fact in value_facts]
    return {
        "answer": " ".join(parts),
        "answer_type": "financial_metric" if value_facts else "unknown",
        "facts_used": [_fact_payload(fact) for fact in facts_used],
        "citations": citations,
        "missing_information": missing,
        "confidence": "high" if value_facts and not missing else ("medium" if value_facts else "low"),
    }


def _requested_financial_metrics(lower_question: str) -> list[str]:
    missing: list[str] = []
    if "revenue" in lower_question or "turnover" in lower_question:
        missing.append("revenue")
    if "ebitda" in lower_question:
        missing.append("EBITDA")
    if "debt" in lower_question or "borrowings" in lower_question:
        missing.append("debt")
    return missing


def _citation(fact: FinancialFact) -> dict:
    return {
        "source_document_id": fact.source_document_id,
        "source_page": fact.source_page,
        "source_quote": fact.source_quote,
    }


def _fact_payload(fact: FinancialFact) -> dict:
    payload = asdict(fact)
    payload["value"] = fact.value.minor_units if fact.value else None
    payload["currency"] = fact.value.currency if fact.value else None
    payload["extraction_confidence"] = str(fact.extraction_confidence)
    return payload

