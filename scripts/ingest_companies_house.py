#!/usr/bin/env python3
"""Create the Gail's Companies House source manifest.

This script is deliberately network-free by default. It records the source set
that should be downloaded or manually curated, with stable source_id values for
downstream extraction and citation.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "dataroom" / "manifest.json"
NOTES_PATH = ROOT / "dataroom" / "source_notes.md"

COMPANY = {
    "legal_name": "GAIL'S LIMITED",
    "company_number": "06055393",
    "jurisdiction": "England and Wales",
    "companies_house_url": "https://find-and-update.company-information.service.gov.uk/company/06055393",
}

REQUIRED_CATEGORIES = [
    "company_profile",
    "filing_history",
    "accounts",
    "charges",
    "management",
    "ownership",
    "news",
]


def source(
    *,
    source_id: str,
    title: str,
    category: str,
    issuer: str,
    source_url: str,
    local_path: str,
    included_reason: str,
    processing_status: str,
    expected_file: str | None = None,
    filing_type: str | None = None,
    filed_at: str | None = None,
    period_end: str | None = None,
    pages: int | None = None,
    notes: str = "",
    retrieved_at: str,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "title": title,
        "category": category,
        "issuer": issuer,
        "retrieved_at": retrieved_at,
        "source_url": source_url,
        "local_path": local_path,
        "included_reason": included_reason,
        "processing_status": processing_status,
        "expected_file": expected_file,
        "filing_type": filing_type,
        "filed_at": filed_at,
        "period_end": period_end,
        "pages": pages,
        "notes": notes,
    }


def build_manifest(generated_at: str) -> dict[str, Any]:
    ch_base = COMPANY["companies_house_url"]
    sources = [
        source(
            source_id="ch-profile-06055393",
            title="Companies House company overview for GAIL'S LIMITED",
            category="company_profile",
            issuer="Companies House",
            source_url=ch_base,
            local_path="dataroom/raw/companies_house/ch-profile-06055393.html",
            included_reason="Baseline legal identity, registered office, status, incorporation date, accounts status, confirmation statement status, and SIC code.",
            processing_status="pending_download",
            expected_file="ch-profile-06055393.html",
            notes="Active private limited company; latest accounts made up to 28 February 2025 on the live overview page.",
            retrieved_at=generated_at,
        ),
        source(
            source_id="ch-filing-history-06055393",
            title="Companies House filing history for GAIL'S LIMITED",
            category="filing_history",
            issuer="Companies House",
            source_url=f"{ch_base}/filing-history",
            local_path="dataroom/raw/companies_house/ch-filing-history-06055393.html",
            included_reason="Authoritative filing index used to identify accounts, guarantee filings, charges, confirmation statements, and officer changes.",
            processing_status="pending_download",
            expected_file="ch-filing-history-06055393.html",
            notes="Source for latest three parent consolidated accounts and recent officer appointment/termination filings.",
            retrieved_at=generated_at,
        ),
        source(
            source_id="ch-parent-accounts-2025",
            title="Parent consolidated accounts, period ending 28 February 2025",
            category="accounts",
            issuer="Companies House",
            source_url=f"{ch_base}/filing-history",
            local_path="dataroom/raw/companies_house/ch-parent-accounts-2025.pdf",
            included_reason="Most recent parent consolidated accounts needed for exact revenue, EBITDA, debt, ownership context, and credit analysis.",
            processing_status="pending_download",
            expected_file="ch-parent-accounts-2025.pdf",
            filing_type="PARENT_ACC",
            filed_at="2025-11-27",
            period_end="2025-02-28",
            pages=55,
            notes="Filing history lists consolidated accounts of parent company for subsidiary company period ending 28/02/25.",
            retrieved_at=generated_at,
        ),
        source(
            source_id="ch-parent-accounts-2024",
            title="Parent consolidated accounts, period ending 29 February 2024",
            category="accounts",
            issuer="Companies House",
            source_url=f"{ch_base}/filing-history",
            local_path="dataroom/raw/companies_house/ch-parent-accounts-2024.pdf",
            included_reason="Second latest parent consolidated accounts for trend analysis and exact comparative financial values.",
            processing_status="pending_download",
            expected_file="ch-parent-accounts-2024.pdf",
            filing_type="PARENT_ACC",
            filed_at="2024-11-25",
            period_end="2024-02-29",
            pages=58,
            notes="Filing history lists consolidated accounts of parent company for subsidiary company period ending 29/02/24.",
            retrieved_at=generated_at,
        ),
        source(
            source_id="ch-parent-accounts-2023",
            title="Parent consolidated accounts, period ending 28 February 2023",
            category="accounts",
            issuer="Companies House",
            source_url=f"{ch_base}/filing-history",
            local_path="dataroom/raw/companies_house/ch-parent-accounts-2023.pdf",
            included_reason="Third latest parent consolidated accounts for required three-year financial coverage.",
            processing_status="pending_download",
            expected_file="ch-parent-accounts-2023.pdf",
            filing_type="PARENT_ACC",
            filed_at="2023-11-28",
            period_end="2023-02-28",
            pages=49,
            notes="Filing history lists consolidated accounts of parent company for subsidiary company period ending 28/02/23.",
            retrieved_at=generated_at,
        ),
        source(
            source_id="ch-charges-register-06055393",
            title="Companies House charges register for GAIL'S LIMITED",
            category="charges",
            issuer="Companies House",
            source_url=f"{ch_base}/charges",
            local_path="dataroom/raw/companies_house/ch-charges-register-06055393.html",
            included_reason="Authoritative list of registered security, charge status, dates, and persons entitled.",
            processing_status="pending_download",
            expected_file="ch-charges-register-06055393.html",
            notes="Charges page shows 6 charges registered: 2 outstanding, 4 satisfied; outstanding 0006 and 0005 name Glas Trust Corporation Limited.",
            retrieved_at=generated_at,
        ),
        source(
            source_id="ch-charge-0006",
            title="Registration of charge 060553930006 created 6 June 2022",
            category="charges",
            issuer="Companies House",
            source_url=f"{ch_base}/charges",
            local_path="dataroom/raw/companies_house/ch-charge-0006.pdf",
            included_reason="Underlying charge instrument for the latest outstanding security and lender/persons entitled review.",
            processing_status="pending_download",
            expected_file="ch-charge-0006.pdf",
            filing_type="MR01",
            filed_at="2022-06-07",
            pages=67,
            notes="Outstanding charge; persons entitled Glas Trust Corporation Limited.",
            retrieved_at=generated_at,
        ),
        source(
            source_id="ch-charge-0005",
            title="Registration of charge 060553930005 created 4 November 2021",
            category="charges",
            issuer="Companies House",
            source_url=f"{ch_base}/charges",
            local_path="dataroom/raw/companies_house/ch-charge-0005.pdf",
            included_reason="Underlying charge instrument for the other outstanding security and lender/persons entitled review.",
            processing_status="pending_download",
            expected_file="ch-charge-0005.pdf",
            filing_type="MR01",
            filed_at="2021-11-05",
            notes="Outstanding charge; persons entitled Glas Trust Corporation Limited.",
            retrieved_at=generated_at,
        ),
        source(
            source_id="ch-officers-06055393",
            title="Companies House officers for GAIL'S LIMITED",
            category="management",
            issuer="Companies House",
            source_url=f"{ch_base}/officers",
            local_path="dataroom/raw/companies_house/ch-officers-06055393.html",
            included_reason="Current directors, secretary, resignations, appointments, and recent management changes.",
            processing_status="pending_download",
            expected_file="ch-officers-06055393.html",
            notes="Active directors observed: Nicholas John Ayerst, Thomas Ralph Molnar, Andy Trigwell. Andy Trigwell also active secretary.",
            retrieved_at=generated_at,
        ),
        source(
            source_id="ch-psc-06055393",
            title="Companies House persons with significant control for GAIL'S LIMITED",
            category="ownership",
            issuer="Companies House",
            source_url=f"{ch_base}/persons-with-significant-control",
            local_path="dataroom/raw/companies_house/ch-psc-06055393.html",
            included_reason="Authoritative PSC/ownership source for ultimate ownership routing and control thresholds.",
            processing_status="pending_download",
            expected_file="ch-psc-06055393.html",
            notes="Active PSC observed: Bread Limited, ownership of shares of 75% or more.",
            retrieved_at=generated_at,
        ),
        source(
            source_id="news-expansion-2025-placeholder",
            title="Curated news placeholder: Gail's expansion and FY2025 sales coverage",
            category="news",
            issuer="Curated public news",
            source_url="https://www.theguardian.com/business/2025/nov/30/bakery-chain-gails-plans-to-open-40-more-outlets-as-sales-soar",
            local_path="dataroom/raw/news/news-expansion-2025-placeholder.md",
            included_reason="Placeholder for curated public coverage of expansion, sales growth, store rollout, and market positioning.",
            processing_status="pending_manual_curation",
            expected_file="news-expansion-2025-placeholder.md",
            notes="Capture bibliographic metadata and short licensing-safe notes manually before use in retrieval.",
            retrieved_at=generated_at,
        ),
        source(
            source_id="news-community-context-2024-placeholder",
            title="Curated news placeholder: Gail's high-street expansion and community context",
            category="news",
            issuer="Curated public news",
            source_url="https://www.theguardian.com/lifeandstyle/article/2024/aug/22/gails-bakery-middle-class-england-political-upmarket-chain-libdems",
            local_path="dataroom/raw/news/news-community-context-2024-placeholder.md",
            included_reason="Placeholder for curated narrative coverage of high-street expansion, brand perception, and community reaction risk.",
            processing_status="pending_manual_curation",
            expected_file="news-community-context-2024-placeholder.md",
            notes="Capture bibliographic metadata and short licensing-safe notes manually before use in retrieval.",
            retrieved_at=generated_at,
        ),
    ]
    return {
        "schema_version": "1.0",
        "generated_at": generated_at,
        "company": COMPANY,
        "coverage": {
            "required_categories": REQUIRED_CATEGORIES,
            "covered_categories": sorted({item["category"] for item in sources}),
            "known_gaps": [
                "PDF documents are referenced but not yet downloaded into dataroom/raw/companies_house.",
                "Curated news items are placeholders pending manual article capture and licensing-safe excerpts.",
                "Financial values must remain unverified until the parent consolidated accounts PDFs are parsed and reviewed.",
            ],
        },
        "sources": sources,
    }


def write_notes(path: Path) -> None:
    path.write_text(
        """# Gail's Dataroom Source Notes

Generated for GAIL'S LIMITED, company number 06055393.

## Companies House coverage

- Company profile: `ch-profile-06055393`
- Filing history: `ch-filing-history-06055393`
- Latest three parent consolidated accounts:
  - `ch-parent-accounts-2025`, period ending 2025-02-28, filed 2025-11-27
  - `ch-parent-accounts-2024`, period ending 2024-02-29, filed 2024-11-25
  - `ch-parent-accounts-2023`, period ending 2023-02-28, filed 2023-11-28
- Charges register and outstanding charge instruments:
  - `ch-charges-register-06055393`
  - `ch-charge-0006`, outstanding, persons entitled Glas Trust Corporation Limited
  - `ch-charge-0005`, outstanding, persons entitled Glas Trust Corporation Limited
- Officers and management:
  - `ch-officers-06055393`
  - Current active directors observed: Nicholas John Ayerst, Thomas Ralph Molnar, Andy Trigwell
  - Current active secretary observed: Andy Trigwell
  - Recent observed management change: Nicholas John Ayerst appointed and Marta Barbara Pogroszewska terminated as director on 2025-07-07
- PSC/ownership:
  - `ch-psc-06055393`
  - Active PSC observed: Bread Limited, ownership of shares of 75% or more

## Curated news placeholders

The manifest intentionally uses placeholders for curated news because automated article copying risks licensing and extraction issues. For each placeholder, add a small Markdown note under `dataroom/raw/news/` containing:

- publication name
- publication date
- article URL
- author if visible
- 3-6 bullet summary in original words, not copied article text
- any exact quoted text only if short and licensing-safe
- relevance to expansion, funding, partnerships, negative events, or credit risk

## Processing policy

Keep `processing_status` as `pending_download` until the raw HTML/PDF is present at `local_path`. Move to `downloaded` when present, `processed` when text/chunks have been extracted into `dataroom/processed/`, and `verified` only after facts used for answers have been checked against the source page/PDF.
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--notes-output", type=Path, default=NOTES_PATH)
    parser.add_argument(
        "--generated-at",
        default=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    args = parser.parse_args()

    manifest = build_manifest(args.generated_at)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    args.notes_output.parent.mkdir(parents=True, exist_ok=True)
    write_notes(args.notes_output)

    print(f"Wrote {args.output}")
    print(f"Wrote {args.notes_output}")
    print(f"Sources: {len(manifest['sources'])}")


if __name__ == "__main__":
    main()
