# Gail's Dataroom Assistant Writeup

This project is a working AI dataroom assistant for GAIL'S LIMITED / Gail's Bakery, company number `06055393`. The goal is to support practical diligence questions over public filings and curated public context while avoiding the most common failure mode in financial RAG systems: plausible but unsupported numbers.

## Approach

The system separates exact facts from narrative synthesis. Companies House filings, charges, officers, PSC information, and curated news are registered in `dataroom/manifest.json` with stable source IDs, local paths, processing status, and inclusion rationale. The current manifest has 12 sources, with 9 indexed through processed snippets. The latest three Companies House parent consolidated accounts PDFs are downloaded but remain pending OCR/table extraction and human review. Structured facts such as revenue, EBITDA, debt, charges, directors, and ownership are stored separately from unstructured text so the assistant can answer deterministic questions without relying on model memory.

The FastAPI backend exposes `/health`, `/sources`, `/sources/{source_id}`, `/ask`, and eval endpoints. `/ask` classifies the question, routes financial/legal/ownership/management questions to structured data first, and uses retrieval plus optional server-side OpenAI synthesis for narrative questions. The Next.js frontend provides a chat interface, suggested diligence questions, loading/error states, and source cards so answers are inspectable.

## Accuracy Decisions

Financial figures are treated as evidence-backed facts, not generated prose. Revenue, EBITDA, and debt must come from structured records with period end, currency, unit, reported-or-computed status, formula where applicable, source ID, page/snippet evidence, extraction confidence, and review status. Exact financial answers pass the reviewed-facts gate only when `reviewed=true` and `usedInAnswers=true`; downloaded OCR output, parser candidates, placeholders, and unreviewed account values are blocked from final answers. EBITDA is reported if present; otherwise it is computed only when every formula component is reviewed and answer-approved. If the dataroom does not support an answer, the assistant should say so and list missing information.

The assistant also uses citation and verifier checks: substantive answers need source IDs from the manifest, numeric claims must be supported by structured facts or charge records, and narrative synthesis receives only retrieved evidence. This keeps the demo credible for lender-style questions where exactness matters.

## Deployment

The app can run as a root Netlify deployment using `netlify.toml`, bundled Netlify functions, and the Next.js frontend build from `frontend/`; alternatively, the backend can run on a Python host with `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`. The production mismatch came from Netlify serving an older frontend-oriented deployment instead of the root deployment with current functions and dataroom artifacts, which left the live UI on old copy and `0 indexed sources`. Production should be checked with `scripts/verify_production.sh`, which verifies the page plus `/api/sources` and requires at least 12 sources and 9 indexed sources. `OPENAI_API_KEY`, `OPENAI_MODEL`, and `USE_OPENAI_SYNTHESIS` are server-only variables for Netlify functions or the backend; the frontend only receives `NEXT_PUBLIC_API_BASE_URL` when it must call a separate backend.

## Future Work

- Better OCR and table extraction for Companies House PDFs.
- A human review queue for extracted financial values before they become answerable facts.
- Scheduled Companies House refresh with manifest diffs and stale-source alerts.
- Full audit trail from source document to chunk, extraction, review, answer, and citation.
- Authentication and access control for non-public demos or client-specific datarooms.
- Expanded lender risk model covering covenants, liquidity, security package, operational risks, and store expansion sensitivity.
