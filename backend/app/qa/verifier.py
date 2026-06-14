from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping


NUMERIC_CLAIM_RE = re.compile(r"(?<![A-Za-z0-9])(?:GBP|\u00a3)?\s*\d[\d,]*(?:\.\d+)?%?")
EBITDA_STATUSES = {"reported", "computed", "unknown"}

PRIVATE_INFORMATION_TERMS = {
    "bank account",
    "sort code",
    "account number",
    "personal address",
    "home address",
    "date of birth",
    "dob",
    "national insurance",
    "passport",
    "salary",
}
COVENANT_TERMS = {"covenant", "covenants", "leverage ratio", "interest cover", "debt service cover"}

QA_UNKNOWN_POLICY = (
    "Answer unknown when the requested fact is outside structured dataroom data, "
    "requires private information, or asks for covenant terms not present in a "
    "structured covenant source. Do not infer from general narrative snippets."
)


@dataclass(frozen=True)
class UnknownPolicyDecision:
    should_answer_unknown: bool
    missing_information: tuple[str, ...] = ()
    reason: str | None = None


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    answer: dict[str, Any]
    errors: tuple[str, ...] = field(default_factory=tuple)


def answer_unknown_policy(question: str, *, has_covenant_data: bool = False) -> UnknownPolicyDecision:
    """Return whether the question must be answered as unknown before synthesis."""

    normalized = question.lower()
    if any(term in normalized for term in PRIVATE_INFORMATION_TERMS):
        return UnknownPolicyDecision(
            should_answer_unknown=True,
            missing_information=("private_information_not_in_dataroom",),
            reason="The question asks for private information that must not be inferred or exposed.",
        )
    if any(term in normalized for term in COVENANT_TERMS) and not has_covenant_data:
        return UnknownPolicyDecision(
            should_answer_unknown=True,
            missing_information=("structured_covenant_terms",),
            reason="The dataroom has no structured covenant source to support covenant claims.",
        )
    return UnknownPolicyDecision(should_answer_unknown=False)


def verify_answer(
    answer: Mapping[str, Any],
    *,
    financial_facts: Iterable[Mapping[str, Any] | Any] = (),
    charges: Iterable[Mapping[str, Any] | Any] = (),
    manifest_sources: Iterable[Mapping[str, Any] | Any] = (),
) -> VerificationResult:
    """Verify dataroom QA output before returning it to a user.

    The verifier is intentionally conservative: numeric claims must match a
    structured financial fact or charge field, every citation must resolve to a
    manifest source, and EBITDA must explicitly disclose whether it is reported,
    computed, or unknown.
    """

    answer_dict = dict(answer)
    errors: list[str] = []

    errors.extend(_missing_citation_sources(answer_dict, manifest_sources))
    errors.extend(_unsupported_numeric_claims(answer_dict, financial_facts, charges))
    errors.extend(_ebitda_status_errors(answer_dict, financial_facts))

    if not errors:
        return VerificationResult(passed=True, answer=answer_dict)

    blocked = {
        **answer_dict,
        "answer": "I cannot provide the drafted answer because it contains unsupported claims.",
        "answer_type": "unknown",
        "confidence": "low",
        "missing_information": _merge_missing_information(answer_dict, errors),
    }
    return VerificationResult(passed=False, answer=blocked, errors=tuple(errors))


def _missing_citation_sources(
    answer: Mapping[str, Any],
    manifest_sources: Iterable[Mapping[str, Any] | Any],
) -> list[str]:
    manifest_ids = {_field(source, "source_id") or _field(source, "id") for source in manifest_sources}
    manifest_ids.discard(None)
    errors: list[str] = []
    for citation in answer.get("citations") or ():
        source_id = _field(citation, "source_id") or _field(citation, "source_document_id")
        if source_id not in manifest_ids:
            errors.append(f"cited source_id is not in manifest: {source_id}")
    return errors


def _unsupported_numeric_claims(
    answer: Mapping[str, Any],
    financial_facts: Iterable[Mapping[str, Any] | Any],
    charges: Iterable[Mapping[str, Any] | Any],
) -> list[str]:
    if answer.get("answer_type") == "unknown":
        return []

    allowed = _allowed_numeric_tokens(financial_facts, charges)
    for fact in answer.get("facts_used") or ():
        if isinstance(fact, Mapping):
            for value in fact.values():
                _add_value_tokens(allowed, value)
                _add_date_tokens(allowed, value)
                _add_identifier_tokens(allowed, value)
    unsupported: list[str] = []
    for claim in NUMERIC_CLAIM_RE.findall(str(answer.get("answer") or "")):
        normalized = _normalize_numeric_claim(claim)
        if normalized and normalized not in allowed:
            unsupported.append(claim.strip())

    if not unsupported:
        return []
    return ["unsupported numeric claims: " + ", ".join(unsupported)]


def _ebitda_status_errors(
    answer: Mapping[str, Any],
    financial_facts: Iterable[Mapping[str, Any] | Any],
) -> list[str]:
    answer_text = str(answer.get("answer") or "").lower()
    facts = list(answer.get("facts_used") or ())
    supplied_facts = list(financial_facts)
    ebitda_facts = [
        fact
        for fact in [*facts, *supplied_facts]
        if str(_field(fact, "metric") or "").lower() == "ebitda"
    ]

    mentions_ebitda = "ebitda" in answer_text or bool(ebitda_facts)
    if not mentions_ebitda:
        return []

    errors: list[str] = []
    statuses = {
        str(_field(fact, "reported_or_computed") or "").lower()
        for fact in ebitda_facts
        if _field(fact, "reported_or_computed") is not None
    }
    invalid_statuses = statuses - EBITDA_STATUSES
    if invalid_statuses:
        errors.append("EBITDA has invalid reported_or_computed status: " + ", ".join(sorted(invalid_statuses)))
    if not statuses and answer.get("answer_type") != "unknown":
        errors.append("EBITDA status is missing")
    if answer.get("answer_type") != "unknown" and not any(status in answer_text for status in EBITDA_STATUSES):
        errors.append("EBITDA answer must state reported, computed, or unknown")
    return errors


def _allowed_numeric_tokens(
    financial_facts: Iterable[Mapping[str, Any] | Any],
    charges: Iterable[Mapping[str, Any] | Any],
) -> set[str]:
    allowed: set[str] = set()
    for fact in financial_facts:
        _add_value_tokens(allowed, _field(fact, "value"))
        _add_date_tokens(allowed, _field(fact, "period_end"))
    for charge in charges:
        _add_identifier_tokens(allowed, _field(charge, "charge_id"))
        _add_date_tokens(allowed, _field(charge, "created_on"))
    return allowed


def _add_value_tokens(allowed: set[str], value: Any) -> None:
    if value is None:
        return
    raw = str(value).replace(",", "").strip()
    if not raw:
        return
    allowed.add(raw)
    try:
        decimal = Decimal(raw)
    except (InvalidOperation, ValueError):
        _add_identifier_tokens(allowed, raw)
        return
    if decimal == decimal.to_integral_value():
        allowed.add(str(decimal.quantize(Decimal("1"))))
    allowed.add(format(decimal.normalize(), "f"))


def _add_date_tokens(allowed: set[str], value: Any) -> None:
    if value is None:
        return
    raw = str(value)
    allowed.update(part.lstrip("0") or "0" for part in re.findall(r"\d+", raw))
    allowed.update(re.findall(r"\d+", raw))


def _add_identifier_tokens(allowed: set[str], value: Any) -> None:
    if value is None:
        return
    text = str(value)
    raw = re.sub(r"\D", "", text)
    if raw:
        allowed.add(raw)
    for part in re.findall(r"\d+", text):
        allowed.add(part)
        allowed.add(part.lstrip("0") or "0")


def _normalize_numeric_claim(value: str) -> str:
    cleaned = value.replace("GBP", "").replace("\u00a3", "").replace(",", "").replace("%", "").strip()
    if not cleaned:
        return ""
    if cleaned.startswith("0") and len(cleaned) > 1 and cleaned.isdigit():
        return cleaned
    try:
        decimal = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return re.sub(r"\D", "", cleaned)
    if decimal == decimal.to_integral_value():
        return str(decimal.quantize(Decimal("1")))
    return format(decimal.normalize(), "f")


def _merge_missing_information(answer: Mapping[str, Any], errors: Iterable[str]) -> list[str]:
    merged = list(answer.get("missing_information") or [])
    for error in errors:
        if error not in merged:
            merged.append(error)
    return merged


def _field(item: Mapping[str, Any] | Any, name: str) -> Any:
    if isinstance(item, Mapping):
        return item.get(name)
    return getattr(item, name, None)
