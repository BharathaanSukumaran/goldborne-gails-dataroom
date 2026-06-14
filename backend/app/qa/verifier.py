from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping


NUMERIC_CLAIM_RE = re.compile(r"(?<![A-Za-z0-9])(?:GBP|\u00a3)?\s*\d[\d,]*(?:\.\d+)?%?")
EBITDA_STATUSES = {"reported", "computed", "unknown", "unavailable"}
STRICT_FINANCIAL_METRICS = {"revenue", "ebitda", "debt"}
LENDER_CONTEXT_TERMS = {"charge", "charges", "security", "lender", "lenders", "holder", "person entitled"}
KNOWN_LENDER_NAMES = {
    "barclays",
    "barclays bank",
    "hsbc",
    "hsbc bank",
    "lloyds",
    "lloyds bank",
    "natwest",
    "national westminster bank",
    "santander",
    "metro bank",
    "bank of ireland",
    "aib",
    "royal bank of scotland",
}
LENDER_ORG_RE = re.compile(
    r"\b(?:[A-Z][A-Za-z&'’.-]+|[A-Z]{2,})"
    r"(?:\s+(?:[A-Z][A-Za-z&'’.-]+|[A-Z]{2,})){0,6}"
    r"\s+(?:Bank|Capital|Credit|Finance|Financial|Funding|Lending|Trust|Trustee|Corporation|PLC|LLP|LLC)\b"
)

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
    errors.extend(_unusable_financial_fact_errors(answer_dict, financial_facts))
    errors.extend(_unsupported_numeric_claims(answer_dict, financial_facts, charges))
    errors.extend(_ebitda_status_errors(answer_dict, financial_facts))
    errors.extend(_unsupported_financial_facts_used(answer_dict, financial_facts))
    errors.extend(_unsupported_covenant_claims(answer_dict))
    errors.extend(_unsupported_lender_claims(answer_dict, charges))

    if not errors:
        return VerificationResult(passed=True, answer=answer_dict)

    blocked = {
        **answer_dict,
        "answer": "I cannot answer this from the current dataroom.",
        "answer_type": "unknown",
        "confidence": "low",
        "missing_information": _merge_missing_information(answer_dict, errors),
    }
    return VerificationResult(passed=False, answer=blocked, errors=tuple(errors))


def _missing_citation_sources(
    answer: Mapping[str, Any],
    manifest_sources: Iterable[Mapping[str, Any] | Any],
) -> list[str]:
    manifest_ids = {_field(source, "source_id") or _field(source, "sourceId") or _field(source, "id") for source in manifest_sources}
    manifest_ids.discard(None)
    errors: list[str] = []
    for citation in answer.get("citations") or ():
        source_id = _field(citation, "source_id") or _field(citation, "sourceId") or _field(citation, "source_document_id")
        if not source_id or source_id not in manifest_ids:
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
        if isinstance(fact, Mapping) and _is_financial_fact(fact) and not _is_usable_financial_fact(fact):
            continue
        if isinstance(fact, Mapping):
            _add_money_minor_tokens(allowed, fact.get("value_minor_units"))
            _add_money_minor_tokens(allowed, fact.get("value"))
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
        if str(_field(fact, "metric") or "").lower() == "ebitda" and (not _is_financial_fact(fact) or _is_usable_financial_fact(fact) or fact in facts)
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


def _unusable_financial_fact_errors(
    answer: Mapping[str, Any],
    financial_facts: Iterable[Mapping[str, Any] | Any],
) -> list[str]:
    answer_facts = list(answer.get("facts_used") or ())
    unusable = [
        fact
        for fact in answer_facts
        if _is_financial_fact(fact) and not _is_usable_financial_fact(fact)
    ]
    if not unusable:
        return []
    metrics = sorted({str(_field(fact, "metric") or "financial_fact") for fact in unusable})
    return ["financial facts are not reviewed and approved for answer use: " + ", ".join(metrics)]


def _is_financial_fact(fact: Mapping[str, Any] | Any) -> bool:
    return str(_field(fact, "metric") or "").lower() in {
        "revenue",
        "turnover",
        "ebitda",
        "debt",
        "borrowings",
        "operating_profit",
        "depreciation",
        "amortisation",
        "impairment",
        "cash",
        "assets",
        "liabilities",
        "profit",
    }


def _is_usable_financial_fact(fact: Mapping[str, Any] | Any) -> bool:
    reviewed = _field(fact, "reviewed")
    used = _field(fact, "used_in_answers")
    if used is None:
        used = _field(fact, "usedInAnswers")
    if used is None:
        return _truthy(reviewed)
    return _truthy(reviewed) and _truthy(used)


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes"}
    return bool(value)


def _allowed_numeric_tokens(
    financial_facts: Iterable[Mapping[str, Any] | Any],
    charges: Iterable[Mapping[str, Any] | Any],
) -> set[str]:
    allowed: set[str] = set()
    for fact in financial_facts:
        if _is_financial_fact(fact) and not _is_usable_financial_fact(fact):
            continue
        _add_value_tokens(allowed, _field(fact, "value"))
        _add_money_minor_tokens(allowed, _field(fact, "value_minor_units"))
        _add_money_minor_tokens(allowed, _field(fact, "value"))
        _add_date_tokens(allowed, _field(fact, "period_end"))
    for charge in charges:
        _add_identifier_tokens(allowed, _field(charge, "charge_id"))
        _add_date_tokens(allowed, _field(charge, "created_on"))
    return allowed


def _unsupported_financial_facts_used(
    answer: Mapping[str, Any],
    financial_facts: Iterable[Mapping[str, Any] | Any],
) -> list[str]:
    if answer.get("answer_type") == "unknown":
        return []

    trusted_keys = {
        _financial_fact_key(fact)
        for fact in financial_facts
        if _is_trusted_financial_fact(fact)
    }
    trusted_keys.discard(None)

    unsupported: list[str] = []
    for fact in answer.get("facts_used") or ():
        metric = str(_field(fact, "metric") or "").lower()
        if metric not in STRICT_FINANCIAL_METRICS:
            continue
        if _financial_fact_key(fact) not in trusted_keys:
            period_end = _field(fact, "period_end") or _field(fact, "periodEnd") or "unknown period"
            unsupported.append(f"{metric} for {period_end}")

    if not unsupported:
        return []
    return ["unsupported financial facts_used: " + ", ".join(unsupported)]


def _unsupported_covenant_claims(answer: Mapping[str, Any]) -> list[str]:
    if answer.get("answer_type") == "unknown":
        return []
    answer_text = str(answer.get("answer") or "").lower()
    mentions_covenant = any(term in answer_text for term in COVENANT_TERMS)
    mentions_headroom = "headroom" in answer_text
    if mentions_covenant or mentions_headroom:
        return ["unsupported covenant/headroom claim"]
    return []


def _unsupported_lender_claims(
    answer: Mapping[str, Any],
    charges: Iterable[Mapping[str, Any] | Any],
) -> list[str]:
    if answer.get("answer_type") == "unknown":
        return []

    answer_text = str(answer.get("answer") or "")
    normalized_answer = answer_text.lower()
    if not any(term in normalized_answer for term in LENDER_CONTEXT_TERMS):
        return []

    allowed_holders = {
        _normalize_name(_field(charge, "holder") or _field(charge, "persons_entitled") or "")
        for charge in charges
    }
    for fact in answer.get("facts_used") or ():
        holder = _field(fact, "holder") or _field(fact, "persons_entitled")
        if isinstance(holder, Iterable) and not isinstance(holder, (str, bytes, Mapping)):
            allowed_holders.update(_normalize_name(item) for item in holder)
        else:
            allowed_holders.add(_normalize_name(holder or ""))
    allowed_holders.discard("")

    candidates = {_normalize_name(match.group(0)) for match in LENDER_ORG_RE.finditer(answer_text)}
    for known_name in KNOWN_LENDER_NAMES:
        if re.search(rf"\b{re.escape(known_name)}\b", normalized_answer):
            candidates.add(_normalize_name(known_name))

    unsupported = [
        candidate
        for candidate in sorted(candidates)
        if candidate and not _name_is_allowed(candidate, allowed_holders)
    ]
    if not unsupported:
        return []
    return ["unsupported lender claim: " + ", ".join(unsupported)]


def _is_trusted_financial_fact(fact: Mapping[str, Any] | Any) -> bool:
    if _is_financial_fact(fact):
        return _is_usable_financial_fact(fact)
    reviewed = _field(fact, "reviewed")
    if reviewed is False or reviewed == 0 or str(reviewed).lower() == "false":
        return False
    return True


def _financial_fact_key(fact: Mapping[str, Any] | Any) -> tuple[str, str, str, str, str] | None:
    metric = str(_field(fact, "metric") or "").lower()
    if not metric:
        return None
    period_end = str(_field(fact, "period_end") or _field(fact, "periodEnd") or "")
    value = _financial_fact_value_token(fact)
    status = str(_field(fact, "reported_or_computed") or _field(fact, "reportedOrComputed") or "").lower()
    source_id = str(_field(fact, "source_document_id") or _field(fact, "sourceId") or _field(fact, "source_id") or "")
    return (metric, period_end, value, status, source_id)


def _financial_fact_value_token(fact: Mapping[str, Any] | Any) -> str:
    value_minor_units = _field(fact, "value_minor_units")
    if value_minor_units is not None:
        return str(value_minor_units).replace(",", "").strip()
    value = _field(fact, "value")
    minor_units = _field(value, "minor_units") if value is not None else None
    if minor_units is not None:
        return str(minor_units).replace(",", "").strip()
    return str(value).replace(",", "").strip() if value is not None else ""


def _normalize_name(value: Any) -> str:
    text = str(value or "").lower()
    text = text.replace("’", "'")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _name_is_allowed(candidate: str, allowed_holders: set[str]) -> bool:
    return any(candidate == allowed or candidate in allowed or allowed in candidate for allowed in allowed_holders)


def _add_money_minor_tokens(allowed: set[str], value: Any) -> None:
    if value is None:
        return
    if isinstance(value, Mapping):
        value = value.get("minor_units")
    raw = str(value).replace(",", "").strip()
    if not raw:
        return
    try:
        minor_units = Decimal(raw)
    except (InvalidOperation, ValueError):
        return
    if minor_units != minor_units.to_integral_value():
        return
    major = minor_units / Decimal("100")
    allowed.add(str(minor_units.quantize(Decimal("1"))))
    allowed.add(format(major, "f"))
    allowed.add(format(major.normalize(), "f"))
    if major == major.to_integral_value():
        allowed.add(str(major.quantize(Decimal("1"))))


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
