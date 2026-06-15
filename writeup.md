# Gail's Dataroom Assistant Writeup

This is a public-source AI dataroom assistant for GAIL'S LIMITED / Gail's Bakery, company number `06055393`. It is designed for diligence-style questions where the right behavior is often to refuse an unsupported answer, especially for exact financial figures.

The system separates ingestion, retrieval, reviewed facts, and AI synthesis. Companies House profile, filing history, accounts metadata, charges, officers, PSC information, and curated public context are registered in `dataroom/manifest.json`. Processing writes page-level snippets or explicit processing-error records under `dataroom/processed/`. Structured facts live separately from text retrieval so financials, charges, ownership, and management questions can be handled deterministically before any model synthesis.

Financial accuracy is gated. Candidate facts in `backend/data/financial_facts.json` are not answerable until a reviewer approves the metric, period, value, source, page, and quote by setting both `reviewed=true` and `usedInAnswers=true`. OpenAI is not trusted for exact revenue, EBITDA, debt, lenders, ownership, directors, or dates. EBITDA is answerable only if it is directly reviewed or computable from complete reviewed operating profit, depreciation, and amortisation facts for the same period.

The current dataroom has `0` reviewed usable financial facts. The latest three parent accounts are registered, but account PDF processing currently records failures rather than usable reviewed values. As a result, revenue, EBITDA, debt, cash, and profit questions should return unavailable with missing-information detail. That is intentional: the app demonstrates safe unknown handling instead of plausible unsupported numbers.

The answer flow is chatbot-first: browser UI to Netlify `/api/ask` or FastAPI `/ask`, question classification, structured facts for exact topics, manifest-backed retrieval for narrative questions, optional server-side OpenAI Responses API synthesis, verifier checks, then a cited answer or unavailable response. `OPENAI_API_KEY` is server-only and never exposed to frontend code.

Local quality gates include backend pytest, ingestion/manifest checks, offline evals, frontend lint/build/smoke tests, raw-label scan, and secret scan through `python3 scripts/test_submission.py`. Production is checked with `scripts/verify_production.sh https://goldborne-gails-dataroom.netlify.app`, which verifies the page, API health, sources, cited supported answers, and unavailable responses for unsupported financial/private questions.

Future work is focused on making the current honest gaps smaller: better OCR and table extraction for Companies House PDFs, a human review UI with audit trail, scheduled Companies House refreshes, broader public-source coverage, authentication for private datarooms, and richer credit analysis once covenant, liquidity, and facility-term sources are actually available.
