from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Iterable


APPROXIMATE_WORDS = {
    "about",
    "approx",
    "approximately",
    "around",
    "circa",
    "estimated",
    "estimate",
    "roughly",
}
MONEY_RE = re.compile(r"(?:£|GBP\s*)\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s*(?:m|million|bn|billion)", re.I)
UNAVAILABLE_RE = re.compile(r"\b(?:unavailable|not available|does not contain|no reviewed|cannot answer)\b", re.I)
GENERIC_CHARGE_LIST_RE = re.compile(
    r"\b(?:two|2)\s+(?:outstanding\s+)?charges\b|"
    r"\bcharges?\s+(?:are\s+)?registered\b|"
    r"\b0605\s*5393\s*0005\b.*\b0605\s*5393\s*0006\b|"
    r"\b0005\b.*\b0006\b",
    re.I | re.S,
)


class EvalFailure(Exception):
    pass


def load_cases(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("cases") if isinstance(data, dict) else data
    if not isinstance(cases, list):
        raise EvalFailure("Golden cases file must contain a list or an object with a 'cases' list.")
    return cases


def load_manifest_source_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = data.get("sources", data) if isinstance(data, dict) else data
    return {source["source_id"] for source in sources if isinstance(source, dict) and source.get("source_id")}


def evaluate_cases(
    cases: Iterable[dict],
    answer_for: Callable[[dict], dict],
    manifest_source_ids: set[str] | None = None,
) -> list[dict]:
    results = []
    for case in cases:
        failures: list[str] = []
        response: dict | None = None
        try:
            response = answer_for(case)
            failures.extend(evaluate_case(case, response, manifest_source_ids or set()))
        except Exception as exc:  # noqa: BLE001 - eval runners should report all case failures.
            failures.append(str(exc))
        results.append(
            {
                "id": case.get("id", "unnamed"),
                "question": case.get("question", ""),
                "passed": not failures,
                "failures": failures,
                "answer_type": response.get("answer_type") if isinstance(response, dict) else None,
                "citations_count": len(response.get("citations", [])) if isinstance(response, dict) else 0,
            }
        )
    return results


def evaluate_case(case: dict, response: dict, manifest_source_ids: set[str]) -> list[str]:
    failures: list[str] = []
    expected = case.get("expect", {})
    answer = str(response.get("answer", ""))
    answer_type = str(response.get("answer_type", ""))
    facts_used = response.get("facts_used") or []
    citations = response.get("citations") or []
    missing_information = response.get("missing_information") or []

    allowed_types = set(expected.get("answer_type_any_of") or [])
    if allowed_types and answer_type not in allowed_types:
        failures.append(f"answer_type {answer_type!r} not in {sorted(allowed_types)!r}")

    for fragment in expected.get("must_contain", []):
        if fragment.lower() not in answer.lower():
            failures.append(f"answer missing required text {fragment!r}")

    for fragment in expected.get("must_not_contain", []):
        if fragment.lower() in answer.lower():
            failures.append(f"answer contains forbidden text {fragment!r}")

    if expected.get("requires_citations") and answer_type != "unknown":
        failures.extend(validate_citations(citations, manifest_source_ids))

    if expected.get("requires_missing_information") and not missing_information:
        failures.append("missing_information must be populated")

    if expected.get("requires_unknown"):
        if answer_type != "unknown":
            failures.append("case must return answer_type='unknown'")
        if not missing_information:
            failures.append("unknown answer must explain missing information")

    if expected.get("forbid_unsupported_money") and answer_type == "unknown":
        if MONEY_RE.search(answer):
            failures.append("unknown answer includes a money-like value")

    if expected.get("forbid_approximation_words", True):
        words = {word.lower() for word in re.findall(r"[A-Za-z]+", answer)}
        used = sorted(words & APPROXIMATE_WORDS)
        if used:
            failures.append("answer uses approximation wording: " + ", ".join(used))

    for metric_rule in expected.get("financial_metrics", []):
        failures.extend(validate_financial_metric(metric_rule, answer, answer_type, facts_used, citations, missing_information))

    charge_rule = expected.get("charge_field")
    if isinstance(charge_rule, dict):
        failures.extend(validate_charge_field(charge_rule, response, answer, answer_type, citations, missing_information, manifest_source_ids))

    return failures


def validate_citations(citations: list[dict], manifest_source_ids: set[str]) -> list[str]:
    failures: list[str] = []
    if not citations:
        return ["non-unknown answer must include at least one citation"]
    for index, citation in enumerate(citations):
        source_id = citation.get("source_id") or citation.get("source_document_id")
        if not source_id:
            failures.append(f"citation {index} is missing source_id")
        elif manifest_source_ids and source_id not in manifest_source_ids:
            failures.append(f"citation {index} source_id {source_id!r} is not in dataroom manifest")
        if not (citation.get("title") or citation.get("source_document_id")):
            failures.append(f"citation {index} is missing title/source_document_id")
        if not (citation.get("snippet") or citation.get("source_quote")):
            failures.append(f"citation {index} is missing snippet/source_quote")
    return failures


def validate_financial_metric(
    rule: dict,
    answer: str,
    answer_type: str,
    facts_used: list[dict],
    citations: list[dict],
    missing_information: list[str],
) -> list[str]:
    metric = rule["metric"]
    exact_major_units = rule.get("exact_major_units")
    mode = rule.get("mode", "exact")
    failures: list[str] = []

    if answer_type == "unknown":
        if mode in {"exact_or_unknown", "unknown_until_extracted"}:
            if not mentions_metric(metric, missing_information):
                failures.append(f"unknown financial answer must list {metric!r} as missing")
            return failures
        failures.append(f"{metric!r} must be answered exactly, not unknown")
        return failures

    matching_facts = [fact for fact in facts_used if str(fact.get("metric", "")).lower() == metric.lower()]
    if not matching_facts:
        failures.append(f"facts_used missing financial metric {metric!r}")

    if not citations:
        failures.append(f"{metric!r} answer is missing citations")

    if exact_major_units is None:
        if mode == "unknown_until_extracted":
            failures.append(f"{metric!r} has no exact value configured, so a non-unknown answer cannot be verified")
        return failures

    expected_decimal = parse_decimal(str(exact_major_units))
    expected_minor_units = int(expected_decimal * Decimal("100"))
    if not any(fact_value_matches(fact.get("value"), expected_decimal, expected_minor_units) for fact in matching_facts):
        failures.append(f"facts_used for {metric!r} does not match exact value {exact_major_units}")
    if format_gbp(expected_decimal) not in answer and str(exact_major_units) not in answer:
        failures.append(f"answer does not include exact value for {metric!r}: {format_gbp(expected_decimal)}")
    return failures


def mentions_metric(metric: str, missing_information: list[str]) -> bool:
    return any(metric.lower() in str(item).lower() for item in missing_information)


def parse_decimal(value: str) -> Decimal:
    try:
        return Decimal(value.replace(",", ""))
    except InvalidOperation as exc:
        raise EvalFailure(f"Invalid exact_major_units value {value!r}") from exc


def fact_value_matches(value: object, expected_decimal: Decimal, expected_minor_units: int) -> bool:
    if value is None:
        return False
    text = str(value).replace(",", "")
    return text in {str(expected_decimal), str(expected_minor_units)}


def format_gbp(value: Decimal) -> str:
    return "£" + f"{value:,.0f}" if value == value.to_integral() else "£" + f"{value:,.2f}"


def validate_charge_field(
    rule: dict,
    response: dict,
    answer: str,
    answer_type: str,
    citations: list[dict],
    missing_information: list[str],
    manifest_source_ids: set[str],
) -> list[str]:
    failures: list[str] = []
    if answer_type not in {"charges", "charges_security", "structured"}:
        failures.append(f"charge field answer_type {answer_type!r} is not a charge answer")

    expected_intent = rule.get("field_intent")
    if expected_intent and response.get("field_intent") != expected_intent:
        failures.append(f"field_intent {response.get('field_intent')!r} != {expected_intent!r}")

    expected_code = normalize_charge_code(rule.get("resolved_charge_code"))
    if expected_code:
        actual_code = normalize_charge_code(response.get("resolved_charge_code"))
        if actual_code != expected_code:
            failures.append(f"resolved_charge_code {actual_code!r} != {expected_code!r}")

    for fragment in rule.get("must_contain", []):
        if fragment.lower() not in answer.lower():
            failures.append(f"charge answer missing required text {fragment!r}")

    if rule.get("requires_unavailable"):
        missing_text = " ".join(str(item) for item in missing_information)
        if not (UNAVAILABLE_RE.search(answer) or UNAVAILABLE_RE.search(missing_text)):
            failures.append("unavailable charge field must explicitly say unavailable/not reviewed")
        if not missing_information:
            failures.append("unavailable charge field must populate missing_information")

    if rule.get("forbid_generic_charge_list") and GENERIC_CHARGE_LIST_RE.search(answer):
        if not rule.get("requires_unavailable") or not UNAVAILABLE_RE.search(answer):
            failures.append("specific charge field answer fell back to a generic charge list")

    source_id = rule.get("expected_source_id")
    if source_id:
        failures.extend(validate_citations(citations, manifest_source_ids))
        if not any((citation.get("source_id") or citation.get("source_document_id")) == source_id for citation in citations):
            failures.append(f"charge answer missing citation to {source_id!r}")

    return failures


def normalize_charge_code(value: object) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())
