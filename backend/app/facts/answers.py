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
    financial_facts so model approximations cannot leak into the answer.
    """

    del model_draft
    period_end = repository.latest_period_end()
    if period_end is None:
        return {
            "answer": "I cannot answer from the dataroom because no financial facts have been extracted.",
            "answer_type": "unknown",
            "facts_used": [],
            "citations": [],
            "missing_information": ["financial_facts"],
            "confidence": "0",
        }

    facts_used: list[FinancialFact] = []
    lower_question = question.lower()
    parts = [f"For the period ended {period_end}:"]
    missing: list[str] = []

    if "revenue" in lower_question or "turnover" in lower_question:
        revenue = repository.get_fact("revenue", period_end)
        if revenue and revenue.value:
            facts_used.append(revenue)
            parts.append(f"revenue was {revenue.value.format()} ({revenue.reported_or_computed}).")
        else:
            missing.append("revenue")

    if "ebitda" in lower_question:
        ebitda = resolve_ebitda(repository, period_end)
        if ebitda.value:
            facts_used.append(ebitda)
            suffix = f" using {ebitda.formula}" if ebitda.reported_or_computed == "computed" else ""
            parts.append(f"EBITDA was {ebitda.value.format()} ({ebitda.reported_or_computed}{suffix}).")
        else:
            missing.append("ebitda")
            parts.append("EBITDA is unknown because it was not reported and could not be computed from complete components.")

    if "debt" in lower_question or "borrowings" in lower_question:
        debt = repository.get_fact("debt", period_end)
        if debt and debt.value:
            facts_used.append(debt)
            parts.append(f"debt was {debt.value.format()} ({debt.reported_or_computed}).")
        else:
            missing.append("debt")

    if not facts_used and not missing:
        return {
            "answer": "I cannot answer this financial question from structured financial facts.",
            "answer_type": "unknown",
            "facts_used": [],
            "citations": [],
            "missing_information": ["supported financial metric"],
            "confidence": "0",
        }

    citations = [_citation(fact) for fact in facts_used]
    return {
        "answer": " ".join(parts),
        "answer_type": "financial_fact" if facts_used else "unknown",
        "facts_used": [_fact_payload(fact) for fact in facts_used],
        "citations": citations,
        "missing_information": missing,
        "confidence": "1" if facts_used and not missing else "0.5",
    }


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
