"""Structured ownership and management facts.

These helpers cover directors/officers, recent appointments/resignations, and
PSC/ownership facts.  They are intended to be used ahead of RAG so management
and ownership answers stay exact and source-cited.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Literal

from backend.app.facts.charges import SourceCitation


OfficerStatus = Literal["active", "resigned"]
PscKind = Literal["individual", "corporate", "legal_person", "super_secure", "unknown"]


@dataclass(frozen=True)
class OfficerFact:
    name: str
    role: str
    appointed_on: date | None
    status: OfficerStatus
    resigned_on: date | None = None
    occupation: str | None = None
    nationality: str | None = None
    citations: tuple[SourceCitation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.citations:
            raise ValueError(f"officer {self.name} must include a source citation")
        if self.status == "resigned" and not self.resigned_on:
            raise ValueError(f"resigned officer {self.name} must include resigned_on")

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "role": self.role,
            "appointed_on": self.appointed_on.isoformat() if self.appointed_on else None,
            "status": self.status,
            "resigned_on": self.resigned_on.isoformat() if self.resigned_on else None,
            "occupation": self.occupation,
            "nationality": self.nationality,
            "citations": [citation.to_dict() for citation in self.citations],
        }


@dataclass(frozen=True)
class PscFact:
    name: str
    kind: PscKind
    notified_on: date | None
    ceased_on: date | None = None
    natures_of_control: tuple[str, ...] = field(default_factory=tuple)
    ownership_summary: str | None = None
    citations: tuple[SourceCitation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.citations:
            raise ValueError(f"PSC {self.name} must include a source citation")
        if not self.natures_of_control and not self.ownership_summary:
            raise ValueError(
                f"PSC {self.name} must include natures_of_control or ownership_summary"
            )

    @property
    def active(self) -> bool:
        return self.ceased_on is None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "kind": self.kind,
            "notified_on": self.notified_on.isoformat() if self.notified_on else None,
            "ceased_on": self.ceased_on.isoformat() if self.ceased_on else None,
            "natures_of_control": list(self.natures_of_control),
            "ownership_summary": self.ownership_summary,
            "citations": [citation.to_dict() for citation in self.citations],
        }


@dataclass(frozen=True)
class ManagementChangeFact:
    change_type: Literal["appointment", "resignation", "psc_added", "psc_ceased"]
    effective_on: date | None
    subject_name: str
    subject_role: str
    details: str
    citations: tuple[SourceCitation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.citations:
            raise ValueError(
                f"management/ownership change for {self.subject_name} must include a citation"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "change_type": self.change_type,
            "effective_on": self.effective_on.isoformat() if self.effective_on else None,
            "subject_name": self.subject_name,
            "subject_role": self.subject_role,
            "details": self.details,
            "citations": [citation.to_dict() for citation in self.citations],
        }


@dataclass(frozen=True)
class StructuredOwnershipAnswer:
    answer: str
    answer_type: Literal[
        "structured_directors",
        "structured_ownership",
        "structured_recent_changes",
    ]
    facts_used: tuple[OfficerFact | PscFact | ManagementChangeFact, ...]
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
    "companies_house_officers_06055393",
    "companies_house_filing_history_appointments_resignations_06055393",
    "companies_house_psc_register_06055393",
)


def build_current_directors_answer(
    officers: Iterable[OfficerFact],
) -> StructuredOwnershipAnswer:
    current_directors = tuple(
        sorted(
            (
                officer
                for officer in officers
                if officer.status == "active" and "director" in officer.role.lower()
            ),
            key=lambda officer: (officer.appointed_on or date.min, officer.name),
        )
    )
    if not current_directors:
        return StructuredOwnershipAnswer(
            answer=(
                "I cannot identify current directors from the structured "
                "dataroom facts currently available."
            ),
            answer_type="structured_directors",
            facts_used=(),
            citations=(),
            missing_information=("Companies House current officer facts",),
            confidence="low",
        )

    lines = ["Current directors identified in the structured dataroom:"]
    for officer in current_directors:
        appointed = (
            f", appointed {officer.appointed_on.isoformat()}"
            if officer.appointed_on
            else ""
        )
        occupation = f", occupation {officer.occupation}" if officer.occupation else ""
        lines.append(f"- {officer.name} ({officer.role}{appointed}{occupation}).")

    return StructuredOwnershipAnswer(
        answer="\n".join(lines),
        answer_type="structured_directors",
        facts_used=current_directors,
        citations=_citations_for(current_directors),
        missing_information=(),
        confidence="high",
    )


def build_ownership_answer(pscs: Iterable[PscFact]) -> StructuredOwnershipAnswer:
    active_pscs = tuple(
        sorted(
            (psc for psc in pscs if psc.active),
            key=lambda psc: (psc.notified_on or date.min, psc.name),
        )
    )
    if not active_pscs:
        return StructuredOwnershipAnswer(
            answer=(
                "I cannot identify active PSC or ownership facts from the "
                "structured dataroom facts currently available."
            ),
            answer_type="structured_ownership",
            facts_used=(),
            citations=(),
            missing_information=("Companies House PSC/ownership facts",),
            confidence="low",
        )

    lines = ["Active PSC/ownership facts identified in the structured dataroom:"]
    for psc in active_pscs:
        controls = (
            "; ".join(psc.natures_of_control)
            if psc.natures_of_control
            else psc.ownership_summary
        )
        notified = f", notified {psc.notified_on.isoformat()}" if psc.notified_on else ""
        lines.append(f"- {psc.name} ({psc.kind}{notified}): {controls}.")

    return StructuredOwnershipAnswer(
        answer="\n".join(lines),
        answer_type="structured_ownership",
        facts_used=active_pscs,
        citations=_citations_for(active_pscs),
        missing_information=(),
        confidence="high",
    )


def build_recent_changes_answer(
    changes: Iterable[ManagementChangeFact],
    *,
    limit: int = 5,
) -> StructuredOwnershipAnswer:
    ordered_changes = tuple(
        sorted(
            changes,
            key=lambda change: (change.effective_on or date.min, change.subject_name),
            reverse=True,
        )
    )[:limit]
    if not ordered_changes:
        return StructuredOwnershipAnswer(
            answer=(
                "I cannot identify recent management or ownership changes from "
                "the structured dataroom facts currently available."
            ),
            answer_type="structured_recent_changes",
            facts_used=(),
            citations=(),
            missing_information=(
                "Companies House officer filing history and PSC change facts",
            ),
            confidence="low",
        )

    lines = ["Recent management or ownership changes identified:"]
    for change in ordered_changes:
        effective = (
            change.effective_on.isoformat() if change.effective_on else "date unknown"
        )
        lines.append(
            f"- {effective}: {change.change_type.replace('_', ' ')} - "
            f"{change.subject_name} ({change.subject_role}); {change.details}."
        )

    return StructuredOwnershipAnswer(
        answer="\n".join(lines),
        answer_type="structured_recent_changes",
        facts_used=ordered_changes,
        citations=_citations_for(ordered_changes),
        missing_information=(),
        confidence="high",
    )


def _citations_for(
    facts: Iterable[OfficerFact | PscFact | ManagementChangeFact],
) -> tuple[SourceCitation, ...]:
    seen: set[tuple[str, int | None, str | None]] = set()
    unique: list[SourceCitation] = []
    for fact in facts:
        for citation in fact.citations:
            key = (citation.source_id, citation.page, citation.quote)
            if key in seen:
                continue
            seen.add(key)
            unique.append(citation)
    return tuple(unique)
