#!/usr/bin/env python3
"""Extract unreviewed candidate legal fields from processed charge instruments.

The extractor is deliberately conservative. It reads only charge-instrument text
sidecars produced from the underlying PDF/text source, never the curated Markdown
summary files. Extracted legal wording is written with fieldReview=false and is
not answerable until review_charge_facts.py approves that specific field.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FACTS = ROOT / "backend" / "data" / "charge_facts.json"
DEFAULT_PROCESSED_DIR = ROOT / "dataroom" / "processed"

LEGAL_FIELDS = [
    "description",
    "shortParticulars",
    "securedAssets",
    "securityType",
    "obligationsSecured",
    "instrumentSummary",
]
ALL_REVIEW_FIELDS = [
    "chargeCode",
    "shortCode",
    "createdDate",
    "deliveredDate",
    "status",
    "satisfiedDate",
    "holder",
    *LEGAL_FIELDS,
]

@dataclass(frozen=True)
class Page:
    number: int | None
    text: str

@dataclass(frozen=True)
class Candidate:
    field: str
    value: str
    source_page: int | None
    quote: str
    confidence: str


def load_facts(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    facts = payload.get("facts", payload) if isinstance(payload, dict) else payload
    if not isinstance(facts, list):
        raise SystemExit("Charge facts file must contain a list or {'facts': [...]} payload")
    return facts


def write_facts(path: Path, facts: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"facts": list(facts)}, indent=2) + "\n", encoding="utf-8")


def load_pages(source_id: str, processed_dir: Path) -> list[Page]:
    pages_path = processed_dir / f"{source_id}.pages.json"
    if pages_path.exists():
        payload = json.loads(pages_path.read_text(encoding="utf-8"))
        return [Page(page.get("page"), page.get("text", "")) for page in payload.get("pages", []) if page.get("text")]

    text_path = processed_dir / f"{source_id}.txt"
    if text_path.exists():
        text = text_path.read_text(encoding="utf-8", errors="ignore")
        parts = text.split("\f") if "\f" in text else [text]
        return [Page(index, part) for index, part in enumerate(parts, start=1) if part.strip()]

    return []


def extract_candidates(pages: list[Page]) -> list[Candidate]:
    if not pages:
        return []
    candidates: list[Candidate] = []
    candidates.extend(find_heading_candidate(pages, "shortParticulars", ["short particulars", "particulars of charge", "property charged", "charged property"]))
    candidates.extend(find_heading_candidate(pages, "description", ["description of instrument", "description of the instrument", "brief description"]))
    candidates.extend(find_keyword_candidate(pages, "obligationsSecured", ["obligations secured", "secured liabilities", "secured obligations", "liabilities secured"]))
    candidates.extend(find_keyword_candidate(pages, "securedAssets", ["all assets", "charged property", "property charged", "undertaking", "assets", "bank accounts", "intellectual property", "shares", "real estate", "land"]))
    candidates.extend(find_keyword_candidate(pages, "instrumentSummary", ["debenture", "charge", "security agreement", "security document"]))

    fixed = find_keyword_candidate(pages, "securityType", ["fixed charge"])
    floating = find_keyword_candidate(pages, "securityType", ["floating charge"])
    if fixed and floating:
        first = min([*fixed, *floating], key=lambda item: item.source_page or 9999)
        candidates.append(Candidate("securityType", "fixed and floating charge wording identified", first.source_page, first.quote, "0.35"))
    elif fixed:
        candidates.append(Candidate("securityType", "fixed charge wording identified", fixed[0].source_page, fixed[0].quote, "0.35"))
    elif floating:
        candidates.append(Candidate("securityType", "floating charge wording identified", floating[0].source_page, floating[0].quote, "0.35"))

    return dedupe_candidates(candidates)


def find_heading_candidate(pages: list[Page], field: str, headings: list[str]) -> list[Candidate]:
    for page in pages:
        lines = normalized_lines(page.text)
        for index, line in enumerate(lines):
            lower = line.lower()
            if any(heading in lower for heading in headings):
                window = " ".join(lines[index:index + 6])
                value = trim_quote(window)
                if meaningful_value(value, headings):
                    return [Candidate(field, value, page.number, value, "0.4")]
    return []


def find_keyword_candidate(pages: list[Page], field: str, keywords: list[str]) -> list[Candidate]:
    for page in pages:
        sentences = split_sentences(page.text)
        for sentence in sentences:
            lower = sentence.lower()
            if any(keyword in lower for keyword in keywords):
                quote = trim_quote(sentence)
                if len(quote) >= 25:
                    return [Candidate(field, quote, page.number, quote, "0.3")]
    return []


def normalized_lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    return [part.strip() for part in re.split(r"(?<=[.;:])\s+", normalized) if part.strip()]


def trim_quote(value: str, limit: int = 700) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit].rstrip()


def meaningful_value(value: str, headings: list[str]) -> bool:
    stripped = value.lower().strip(" :-")
    return len(stripped) > 20 and stripped not in set(headings)


def dedupe_candidates(candidates: list[Candidate]) -> list[Candidate]:
    by_field: dict[str, Candidate] = {}
    for candidate in candidates:
        by_field.setdefault(candidate.field, candidate)
    return list(by_field.values())


def merge_candidates(fact: dict[str, Any], candidates: list[Candidate]) -> int:
    field_review = fact.setdefault("fieldReview", {})
    for field in ALL_REVIEW_FIELDS:
        field_review.setdefault(field, False)
    field_evidence = fact.setdefault("fieldEvidence", {})
    changed = 0
    for candidate in candidates:
        if field_review.get(candidate.field) is True:
            continue
        if fact.get(candidate.field) != candidate.value:
            fact[candidate.field] = candidate.value
            changed += 1
        field_review[candidate.field] = False
        field_evidence[candidate.field] = {
            "sourceId": fact.get("sourceId"),
            "sourcePage": candidate.source_page,
            "sourceQuote": candidate.quote,
            "reviewed": False,
            "extractionConfidence": candidate.confidence,
        }
    return changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--facts", type=Path, default=DEFAULT_FACTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_FACTS)
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_DIR)
    args = parser.parse_args()

    facts = load_facts(args.facts)
    extracted = 0
    changed = 0
    for fact in facts:
        source_id = fact.get("sourceId")
        if not str(source_id).startswith("ch-charge-"):
            continue
        candidates = extract_candidates(load_pages(str(source_id), args.processed_dir))
        extracted += len(candidates)
        changed += merge_candidates(fact, candidates)

    write_facts(args.output, facts)
    print(f"Wrote {len(facts)} charge fact records to {args.output}")
    print(f"Extracted candidate legal fields: {extracted}")
    print(f"Updated unreviewed field values: {changed}")
    print("Reviewed usable legal fields: 0. Parser output is never auto-approved; use review_charge_facts.py after human review.")


if __name__ == "__main__":
    main()
