# QA UI cleanup report

Checked rendered frontend surfaces for raw internal labels listed in `instructions.md`. Frontend display text is routed through `frontend/lib/display-labels.ts`, and reviewed facts now use an explicit curated renderer instead of generic object-entry rendering.

Mapped labels:

- `company_profile` -> Company profile
- `financial_filings` -> Financial filings
- `charges_register` -> Charges & security
- `ownership_management` -> Ownership & management
- `news_events` -> News & events
- `industry_context` -> Market context
- `source_count` -> Documents
- `indexed_count` -> Ready documents
- `indexed_source_count` -> Ready documents
- `usedInAnswers` / `used_in_answers` -> Available for answers
- `reviewed` -> Source checked
- `sourceId` / `source_id` -> Source
- `workspaceId` / `workspace_id` -> Workspace
- `periodEnd` / `period_end` -> Period end
- `reportedOrComputed` / `reported_or_computed` -> Basis
- `processing_status` / `source_status` -> Status
- `included_reason` -> Why included
- `local_path` -> Local file
- `financial_facts` -> Financial figures

Hidden or suppressed in rendered UI:

- Raw source identifiers are used only for React keys/API matching and are not shown as fallback titles.
- Local file paths and workspace IDs are not rendered in source cards or the dataroom drawer.
- Reviewed-fact objects are no longer rendered with arbitrary keys; the drawer shows only Fact, Value, Period, Source, and Status.
- The dataroom drawer stays closed by default and no longer opens automatically after answers.

Allowed remaining occurrences are internal API contract keys in TypeScript types, API parsing, field lookup arrays, display-label dictionaries, QA checks, backend files, and data files. Backend/API contract fields were not changed.
