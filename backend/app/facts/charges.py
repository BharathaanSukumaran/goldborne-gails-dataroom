"""Structured handling for Companies House charge facts.

The assistant should use these records before retrieval when answering
questions about security, charge holders, and charge status.  The functions in
this module are deliberately deterministic: if the seeded/extracted facts do
not include cited evidence, they fail instead of producing uncited claims.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, Literal


ChargeStatus = Literal["outstanding", "satisfied", "part-satisfied", "unknown"]
ChargeField = Literal[
    "chargeCode",
    "shortCode",
    "createdDate",
    "deliveredDate",
    "status",
    "satisfiedDate",
    "holder",
    "description",
    "shortParticulars",
    "securedAssets",
    "securityType",
    "obligationsSecured",
    "instrumentSummary",
]

CORE_REVIEWED_FIELDS: frozenset[str] = frozenset(
    {"chargeCode", "shortCode", "createdDate", "status", "satisfiedDate", "holder"}
)


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
    """A Companies House charge entry with field-level review gates."""

    charge_id: str
    created_on: date | None
    registered_on: date | None
    status: ChargeStatus
    persons_entitled: tuple[str, ...]
    workspace_id: str = "gails-limited"
    short_code: str | None = None
    delivered_on: date | None = None
    classification: str | None = None
    description: str | None = None
    short_particulars: str | None = None
    secured_assets: str | None = None
    security_type: str | None = None
    obligations_secured: str | None = None
    instrument_summary: str | None = None
    satisfied_on: date | None = None
    source_id: str | None = None
    source_page: int | None = None
    source_quote: str | None = None
    reviewed: bool = True
    field_review: dict[str, bool] = field(default_factory=dict)
    citations: tuple[SourceCitation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.citations:
            raise ValueError(f"charge {self.charge_id} must include a source citation")
        if not self.persons_entitled:
            raise ValueError(f"charge {self.charge_id} must include holder/person entitled data")
        normalized = _default_field_review(self)
        normalized.update(self.field_review)
        object.__setattr__(self, "field_review", normalized)

    def to_dict(self) -> dict[str, object]:
        return {
            "workspace_id": self.workspace_id,
            "charge_id": self.charge_id,
            "short_code": self.short_code,
            "created_on": self.created_on.isoformat() if self.created_on else None,
            "registered_on": self.registered_on.isoformat() if self.registered_on else None,
            "delivered_on": self.delivered_on.isoformat() if self.delivered_on else None,
            "status": self.status,
            "persons_entitled": list(self.persons_entitled),
            "classification": self.classification,
            "description": self.description,
            "short_particulars": self.short_particulars,
            "secured_assets": self.secured_assets,
            "security_type": self.security_type,
            "obligations_secured": self.obligations_secured,
            "instrument_summary": self.instrument_summary,
            "satisfied_on": self.satisfied_on.isoformat() if self.satisfied_on else None,
            "source_id": self.source_id,
            "source_page": self.source_page,
            "source_quote": self.source_quote,
            "reviewed": self.reviewed,
            "field_review": dict(self.field_review),
            "citations": [citation.to_dict() for citation in self.citations],
        }

    def reviewed_value(self, field_name: ChargeField) -> object | None:
        """Return a field value only when that specific field is reviewed."""

        if not self.reviewed or not self.field_review.get(field_name, False):
            return None
        value = _field_value(self, field_name)
        if value in ("", (), []):
            return None
        return value

    def is_field_answerable(self, field_name: ChargeField) -> bool:
        return self.reviewed_value(field_name) is not None


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
        description_value = charge.reviewed_value("description")
        description = f" - {description_value}" if description_value else ""
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


def load_charge_facts_json(path: str | Path) -> list[ChargeFact]:
    """Load expanded charge facts from JSON while preserving field review gates."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    records = payload.get("facts", payload) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError("charge facts JSON must be a list or an object with a facts list")
    return [_record_to_charge_fact(record) for record in records]


def _record_to_charge_fact(record: dict) -> ChargeFact:
    source_id = record["sourceId"]
    source_quote = record["sourceQuote"]
    source_page = record.get("sourcePage")
    citation = SourceCitation(
        source_id=source_id,
        title=record.get("sourceTitle", source_id),
        url=record.get("sourceUrl", ""),
        page=source_page,
        quote=source_quote,
    )
    return ChargeFact(
        workspace_id=record.get("workspaceId", "gails-limited"),
        charge_id=record.get("displayChargeCode") or record["chargeCode"],
        short_code=record.get("shortCode"),
        created_on=_date_or_none(record.get("createdDate")),
        registered_on=_date_or_none(record.get("registeredDate")),
        delivered_on=_date_or_none(record.get("deliveredDate")),
        status=record.get("status", "unknown"),
        persons_entitled=(record["holder"],),
        description=record.get("description"),
        short_particulars=record.get("shortParticulars"),
        secured_assets=record.get("securedAssets"),
        security_type=record.get("securityType"),
        obligations_secured=record.get("obligationsSecured"),
        instrument_summary=record.get("instrumentSummary"),
        satisfied_on=_date_or_none(record.get("satisfiedDate")),
        source_id=source_id,
        source_page=source_page,
        source_quote=source_quote,
        reviewed=bool(record.get("reviewed", False)),
        field_review=dict(record.get("fieldReview", {})),
        citations=(citation,),
    )


def _date_or_none(value: object) -> date | None:
    return date.fromisoformat(value) if isinstance(value, str) and value else None


def _default_field_review(charge: ChargeFact) -> dict[str, bool]:
    values = {
        "chargeCode": charge.charge_id,
        "shortCode": charge.short_code,
        "createdDate": charge.created_on,
        "deliveredDate": charge.delivered_on,
        "status": charge.status if charge.status != "unknown" else None,
        "satisfiedDate": charge.satisfied_on,
        "holder": charge.persons_entitled,
        "description": charge.description,
        "shortParticulars": charge.short_particulars,
        "securedAssets": charge.secured_assets,
        "securityType": charge.security_type,
        "obligationsSecured": charge.obligations_secured,
        "instrumentSummary": charge.instrument_summary,
    }
    return {
        field_name: field_name in CORE_REVIEWED_FIELDS and values[field_name] not in (None, "", (), [])
        for field_name in values
    }


def _field_value(charge: ChargeFact, field_name: str) -> object | None:
    values = {
        "chargeCode": charge.charge_id,
        "shortCode": charge.short_code,
        "createdDate": charge.created_on.isoformat() if charge.created_on else None,
        "deliveredDate": charge.delivered_on.isoformat() if charge.delivered_on else None,
        "status": charge.status if charge.status != "unknown" else None,
        "satisfiedDate": charge.satisfied_on.isoformat() if charge.satisfied_on else None,
        "holder": charge.persons_entitled,
        "description": charge.description,
        "shortParticulars": charge.short_particulars,
        "securedAssets": charge.secured_assets,
        "securityType": charge.security_type,
        "obligationsSecured": charge.obligations_secured,
        "instrumentSummary": charge.instrument_summary,
    }
    return values[field_name]
