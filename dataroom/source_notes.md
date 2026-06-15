# Gail's Dataroom Source Notes

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

Keep `processing_status` as `pending_download` until the raw HTML/PDF is present at `local_path`. Move to `downloaded` when present, `processed` when text/chunks have been extracted into `dataroom/processed/`, and `verified` only after facts used for answers have been checked against the source page/PDF. `source_status` is the UI-friendly roll-up: `pending`, `processed`, or `verified`; downloaded but unprocessed files remain `pending`.
