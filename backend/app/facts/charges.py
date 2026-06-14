"""Structured handling for Companies House charge facts.

The assistant should use these records before retrieval when answering
questions about security, charge holders, and charge status.  The functions in
this module are deliberately deterministic: if the seeded/extracted facts do
not include cited evidence, they fail instead of producing uncited claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Literal


ChargeStatus = Literal["outstanding", "satisfied", "part-satisfied", "unknown"]


@dataclass(frozen=True)
class SourceCitation:
    """A specific citation back to a dataroom source."""

    source_id: str
    title: str
    url: str
    page: int | None = None
    quote: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "url": self.url,
            "page": self.page,
            "quote": self.quote,
        }


@dataclass(frozen=True)
class ChargeFact:
    """A Companies House charge entry with holders/persons entitled."""

    charge_id: str
    created_on: date | None
    registered_on: date | None
    status: ChargeStatus
    persons_entitled: tuple[str, ...]
    classification: str | None = None
    description: str | None = None
    satisfied_on: date | None = None
    citations: tuple[SourceCitation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.citations:
            raise ValueError(f"charge {self.charge_id} must include a source citation")
        if not self.persons_entitled:
            raise ValueError(f"charge {self.charge_id} must include holder/person entitled data")

    def to_dict(self) -> dict[str, object]:
        return {
            "charge_id": self.charge_id,
            "created_on": self.created_on.isoformat() if self.created_on else None,
            "registered_on": self.registered_on.isoformat() if self.registered_on else None,
            "status": self.status,
            "persons_entitled": list(self.persons_entitled),
            "classification": self.classification,
            "description": self.description,
            "satisfied_on": self.satisfied_on.isoformat() if self.satisfied_on else None,
            "citations": [citation.to_dict() for citation in self.citations],
        }


@dataclass(frozen=True)
class StructuredChargeAnswer:
    answer: str
    answer_type: Literal["structured_charges"]
    facts_used: tuple[ChargeFact, ...]
    citations: tuple[SourceCitation, ...]
    missing_information: tuple[str, ...]
    confidence: Literal["high", "medium", "low"]

    def to_dict(self) -> dict[str, object]:
        return {
            "answer": self.answer,
            "answer_type": self.answer_type,
            "facts_used": [fact.to_dict() for fact in self.facts_used],
            "citations": [citation.to_dict() for citation in self.citations],
            "missing_information": list(self.missing_information),
            "confidence": self.confidence,
        }


SEED_DATA_SUGGESTIONS: tuple[str, ...] = (
    "companies_house_charge_register_profile_06055393",
    "companies_house_charge_detail_06055393_<charge_id>",
)


def build_charges_answer(charges: Iterable[ChargeFact]) -> StructuredChargeAnswer:
    """Return a cited answer for registered charges and holders.

    The caller should pass facts extracted from Companies House charge register
    and charge-detail documents.  When no charges are available, the answer is
    explicit about the evidence gap instead of inferring that no charges exist.
    """

    ordered_charges = tuple(sorted(charges, key=_charge_sort_key))
    if not ordered_charges:
        return StructuredChargeAnswer(
            answer=(
                "I cannot identify registered charges from the structured "
                "dataroom facts currently available."
            ),
            answer_type="structured_charges",
            facts_used=(),
            citations=(),
            missing_information=("Companies House charge register facts",),
            confidence="low",
        )

    citations = _dedupe_citations(
        citation for charge in ordered_charges for citation in charge.citations
    )
    lines = ["Registered charges identified in the structured dataroom:"]
    for charge in ordered_charges:
        holder_text = ", ".join(charge.persons_entitled)
        dates = []
        if charge.created_on:
            dates.append(f"created {charge.created_on.isoformat()}")
        if charge.registered_on:
            dates.append(f"registered {charge.registered_on.isoformat()}")
        if charge.satisfied_on:
            dates.append(f"satisfied {charge.satisfied_on.isoformat()}")
        date_text = f" ({'; '.join(dates)})" if dates else ""
        description = f" - {charge.description}" if charge.description else ""
        lines.append(
            f"- Charge {charge.charge_id}: {charge.status}{date_text}; "
            f"holder/person entitled: {holder_text}{description}."
        )

    return StructuredChargeAnswer(
        answer="\n".join(lines),
        answer_type="structured_charges",
        facts_used=ordered_charges,
        citations=citations,
        missing_information=(),
        confidence="high",
    )


def _charge_sort_key(charge: ChargeFact) -> tuple[date, str]:
    fallback = date.min
    return (charge.created_on or charge.registered_on or fallback, charge.charge_id)


def _dedupe_citations(citations: Iterable[SourceCitation]) -> tuple[SourceCitation, ...]:
    seen: set[tuple[str, int | None, str | None]] = set()
    unique: list[SourceCitation] = []
    for citation in citations:
        key = (citation.source_id, citation.page, citation.quote)
        if key in seen:
            continue
        seen.add(key)
        unique.append(citation)
    return tuple(unique)
