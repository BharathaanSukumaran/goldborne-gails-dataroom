export const manifest = {
  "schema_version": "1.0",
  "generated_at": "2026-06-14T00:00:00Z",
  "company": {
    "legal_name": "GAIL'S LIMITED",
    "company_number": "06055393",
    "jurisdiction": "England and Wales",
    "companies_house_url": "https://find-and-update.company-information.service.gov.uk/company/06055393"
  },
  "coverage": {
    "required_categories": [
      "company_profile",
      "filing_history",
      "accounts",
      "charges",
      "management",
      "ownership",
      "news"
    ],
    "covered_categories": [
      "accounts",
      "charges",
      "company_profile",
      "filing_history",
      "management",
      "news",
      "ownership"
    ],
    "known_gaps": [
      "PDF documents are referenced but not yet downloaded into dataroom/raw/companies_house.",
      "Curated news items are placeholders pending manual article capture and licensing-safe excerpts.",
      "Financial values must remain unverified until the parent consolidated accounts PDFs are parsed and reviewed."
    ]
  },
  "sources": [
    {
      "source_id": "ch-profile-06055393",
      "title": "Companies House company overview for GAIL'S LIMITED",
      "category": "company_profile",
      "issuer": "Companies House",
      "retrieved_at": "2026-06-14T00:00:00Z",
      "source_url": "https://find-and-update.company-information.service.gov.uk/company/06055393",
      "local_path": "dataroom/raw/companies_house/ch-profile-06055393.html",
      "included_reason": "Baseline legal identity, registered office, status, incorporation date, accounts status, confirmation statement status, and SIC code.",
      "processing_status": "pending_download",
      "expected_file": "ch-profile-06055393.html",
      "filing_type": null,
      "filed_at": null,
      "period_end": null,
      "pages": null,
      "notes": "Active private limited company; latest accounts made up to 28 February 2025 on the live overview page."
    },
    {
      "source_id": "ch-filing-history-06055393",
      "title": "Companies House filing history for GAIL'S LIMITED",
      "category": "filing_history",
      "issuer": "Companies House",
      "retrieved_at": "2026-06-14T00:00:00Z",
      "source_url": "https://find-and-update.company-information.service.gov.uk/company/06055393/filing-history",
      "local_path": "dataroom/raw/companies_house/ch-filing-history-06055393.html",
      "included_reason": "Authoritative filing index used to identify accounts, guarantee filings, charges, confirmation statements, and officer changes.",
      "processing_status": "pending_download",
      "expected_file": "ch-filing-history-06055393.html",
      "filing_type": null,
      "filed_at": null,
      "period_end": null,
      "pages": null,
      "notes": "Source for latest three parent consolidated accounts and recent officer appointment/termination filings."
    },
    {
      "source_id": "ch-parent-accounts-2025",
      "title": "Parent consolidated accounts, period ending 28 February 2025",
      "category": "accounts",
      "issuer": "Companies House",
      "retrieved_at": "2026-06-14T00:00:00Z",
      "source_url": "https://find-and-update.company-information.service.gov.uk/company/06055393/filing-history",
      "local_path": "dataroom/raw/companies_house/ch-parent-accounts-2025.pdf",
      "included_reason": "Most recent parent consolidated accounts needed for exact revenue, EBITDA, debt, ownership context, and credit analysis.",
      "processing_status": "pending_download",
      "expected_file": "ch-parent-accounts-2025.pdf",
      "filing_type": "PARENT_ACC",
      "filed_at": "2025-11-27",
      "period_end": "2025-02-28",
      "pages": 55,
      "notes": "Filing history lists consolidated accounts of parent company for subsidiary company period ending 28/02/25."
    },
    {
      "source_id": "ch-parent-accounts-2024",
      "title": "Parent consolidated accounts, period ending 29 February 2024",
      "category": "accounts",
      "issuer": "Companies House",
      "retrieved_at": "2026-06-14T00:00:00Z",
      "source_url": "https://find-and-update.company-information.service.gov.uk/company/06055393/filing-history",
      "local_path": "dataroom/raw/companies_house/ch-parent-accounts-2024.pdf",
      "included_reason": "Second latest parent consolidated accounts for trend analysis and exact comparative financial values.",
      "processing_status": "pending_download",
      "expected_file": "ch-parent-accounts-2024.pdf",
      "filing_type": "PARENT_ACC",
      "filed_at": "2024-11-25",
      "period_end": "2024-02-29",
      "pages": 58,
      "notes": "Filing history lists consolidated accounts of parent company for subsidiary company period ending 29/02/24."
    },
    {
      "source_id": "ch-parent-accounts-2023",
      "title": "Parent consolidated accounts, period ending 28 February 2023",
      "category": "accounts",
      "issuer": "Companies House",
      "retrieved_at": "2026-06-14T00:00:00Z",
      "source_url": "https://find-and-update.company-information.service.gov.uk/company/06055393/filing-history",
      "local_path": "dataroom/raw/companies_house/ch-parent-accounts-2023.pdf",
      "included_reason": "Third latest parent consolidated accounts for required three-year financial coverage.",
      "processing_status": "pending_download",
      "expected_file": "ch-parent-accounts-2023.pdf",
      "filing_type": "PARENT_ACC",
      "filed_at": "2023-11-28",
      "period_end": "2023-02-28",
      "pages": 49,
      "notes": "Filing history lists consolidated accounts of parent company for subsidiary company period ending 28/02/23."
    },
    {
      "source_id": "ch-charges-register-06055393",
      "title": "Companies House charges register for GAIL'S LIMITED",
      "category": "charges",
      "issuer": "Companies House",
      "retrieved_at": "2026-06-14T00:00:00Z",
      "source_url": "https://find-and-update.company-information.service.gov.uk/company/06055393/charges",
      "local_path": "dataroom/raw/companies_house/ch-charges-register-06055393.html",
      "included_reason": "Authoritative list of registered security, charge status, dates, and persons entitled.",
      "processing_status": "pending_download",
      "expected_file": "ch-charges-register-06055393.html",
      "filing_type": null,
      "filed_at": null,
      "period_end": null,
      "pages": null,
      "notes": "Charges page shows 6 charges registered: 2 outstanding, 4 satisfied; outstanding 0006 and 0005 name Glas Trust Corporation Limited."
    },
    {
      "source_id": "ch-charge-0006",
      "title": "Registration of charge 060553930006 created 6 June 2022",
      "category": "charges",
      "issuer": "Companies House",
      "retrieved_at": "2026-06-14T00:00:00Z",
      "source_url": "https://find-and-update.company-information.service.gov.uk/company/06055393/charges",
      "local_path": "dataroom/raw/companies_house/ch-charge-0006.pdf",
      "included_reason": "Underlying charge instrument for the latest outstanding security and lender/persons entitled review.",
      "processing_status": "pending_download",
      "expected_file": "ch-charge-0006.pdf",
      "filing_type": "MR01",
      "filed_at": "2022-06-07",
      "period_end": null,
      "pages": 67,
      "notes": "Outstanding charge; persons entitled Glas Trust Corporation Limited."
    },
    {
      "source_id": "ch-charge-0005",
      "title": "Registration of charge 060553930005 created 4 November 2021",
      "category": "charges",
      "issuer": "Companies House",
      "retrieved_at": "2026-06-14T00:00:00Z",
      "source_url": "https://find-and-update.company-information.service.gov.uk/company/06055393/charges",
      "local_path": "dataroom/raw/companies_house/ch-charge-0005.pdf",
      "included_reason": "Underlying charge instrument for the other outstanding security and lender/persons entitled review.",
      "processing_status": "pending_download",
      "expected_file": "ch-charge-0005.pdf",
      "filing_type": "MR01",
      "filed_at": "2021-11-05",
      "period_end": null,
      "pages": null,
      "notes": "Outstanding charge; persons entitled Glas Trust Corporation Limited."
    },
    {
      "source_id": "ch-officers-06055393",
      "title": "Companies House officers for GAIL'S LIMITED",
      "category": "management",
      "issuer": "Companies House",
      "retrieved_at": "2026-06-14T00:00:00Z",
      "source_url": "https://find-and-update.company-information.service.gov.uk/company/06055393/officers",
      "local_path": "dataroom/raw/companies_house/ch-officers-06055393.html",
      "included_reason": "Current directors, secretary, resignations, appointments, and recent management changes.",
      "processing_status": "pending_download",
      "expected_file": "ch-officers-06055393.html",
      "filing_type": null,
      "filed_at": null,
      "period_end": null,
      "pages": null,
      "notes": "Active directors observed: Nicholas John Ayerst, Thomas Ralph Molnar, Andy Trigwell. Andy Trigwell also active secretary."
    },
    {
      "source_id": "ch-psc-06055393",
      "title": "Companies House persons with significant control for GAIL'S LIMITED",
      "category": "ownership",
      "issuer": "Companies House",
      "retrieved_at": "2026-06-14T00:00:00Z",
      "source_url": "https://find-and-update.company-information.service.gov.uk/company/06055393/persons-with-significant-control",
      "local_path": "dataroom/raw/companies_house/ch-psc-06055393.html",
      "included_reason": "Authoritative PSC/ownership source for ultimate ownership routing and control thresholds.",
      "processing_status": "pending_download",
      "expected_file": "ch-psc-06055393.html",
      "filing_type": null,
      "filed_at": null,
      "period_end": null,
      "pages": null,
      "notes": "Active PSC observed: Bread Limited, ownership of shares of 75% or more."
    },
    {
      "source_id": "news-expansion-2025-placeholder",
      "title": "Curated news placeholder: Gail's expansion and FY2025 sales coverage",
      "category": "news",
      "issuer": "Curated public news",
      "retrieved_at": "2026-06-14T00:00:00Z",
      "source_url": "https://www.theguardian.com/business/2025/nov/30/bakery-chain-gails-plans-to-open-40-more-outlets-as-sales-soar",
      "local_path": "dataroom/raw/news/news-expansion-2025-placeholder.md",
      "included_reason": "Placeholder for curated public coverage of expansion, sales growth, store rollout, and market positioning.",
      "processing_status": "pending_manual_curation",
      "expected_file": "news-expansion-2025-placeholder.md",
      "filing_type": null,
      "filed_at": null,
      "period_end": null,
      "pages": null,
      "notes": "Capture bibliographic metadata and short licensing-safe notes manually before use in retrieval."
    },
    {
      "source_id": "news-community-context-2024-placeholder",
      "title": "Curated news placeholder: Gail's high-street expansion and community context",
      "category": "news",
      "issuer": "Curated public news",
      "retrieved_at": "2026-06-14T00:00:00Z",
      "source_url": "https://www.theguardian.com/lifeandstyle/article/2024/aug/22/gails-bakery-middle-class-england-political-upmarket-chain-libdems",
      "local_path": "dataroom/raw/news/news-community-context-2024-placeholder.md",
      "included_reason": "Placeholder for curated narrative coverage of high-street expansion, brand perception, and community reaction risk.",
      "processing_status": "pending_manual_curation",
      "expected_file": "news-community-context-2024-placeholder.md",
      "filing_type": null,
      "filed_at": null,
      "period_end": null,
      "pages": null,
      "notes": "Capture bibliographic metadata and short licensing-safe notes manually before use in retrieval."
    }
  ]
} as const;

export const charges = [
  { charge_code: "0605 5393 0006", created_date: "2022-06-06", status: "outstanding", holder: "Glas Trust Corporation Limited", source_id: "ch-charge-0006", source_quote: "Companies House charges metadata records this charge as outstanding and held by Glas Trust Corporation Limited." },
  { charge_code: "0605 5393 0005", created_date: "2021-11-04", status: "outstanding", holder: "Glas Trust Corporation Limited", source_id: "ch-charge-0005", source_quote: "Companies House charges metadata records this charge as outstanding and held by Glas Trust Corporation Limited." }
];

export const officers = [
  { name: "Nicholas John Ayerst", role: "Director", status: "current", source_id: "ch-officers-06055393" },
  { name: "Thomas Ralph Molnar", role: "Director", status: "current", source_id: "ch-officers-06055393" },
  { name: "Andy Trigwell", role: "Director", status: "current", source_id: "ch-officers-06055393" }
];

export const ownership = { owner_name: "Bread Limited", control_type: "person with significant control", percentage_band: "75% or more", status: "active", source_id: "ch-psc-06055393" };

export function sourceById(sourceId: string) {
  return manifest.sources.find((source) => source.source_id === sourceId);
}

export function citation(sourceId: string, snippet?: string) {
  const source = sourceById(sourceId);
  return {
    source_id: sourceId,
    title: source?.title ?? sourceId,
    category: source?.category ?? "unknown",
    source_url: source?.source_url ?? "",
    page: null,
    snippet
  };
}
