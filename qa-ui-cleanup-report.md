# QA UI cleanup report

Checked rendered frontend surfaces for raw internal labels and routed display text through `frontend/lib/display-labels.ts`.

Removed or mapped from user-facing UI:

- Source categories: `company_profile`, `financial_filings`, `charges_register`, `ownership_management`, `news_events`
- Count/fact fields: `source_count`, `indexed_count`, `usedInAnswers`, `reviewed=`, `workspaceId`, `sourceId`, `periodEnd`, `reportedOrComputed`

Remaining frontend occurrences are internal keys for API payloads, TypeScript shapes, filter matching, label dictionaries, data attributes, or QA checks. Backend and dataroom files were not changed.
