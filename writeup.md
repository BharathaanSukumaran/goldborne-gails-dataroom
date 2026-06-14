# Gail's Dataroom Assistant Writeup

This project is a working AI dataroom assistant for GAIL'S LIMITED / Gail's Bakery, company number `06055393`. The goal is to support practical diligence questions over public filings and curated public context while avoiding the most common failure mode in financial RAG systems: plausible but unsupported numbers.

## Approach

The system separates exact facts from narrative synthesis. Companies House filings, charges, officers, PSC information, and curated news are registered in `dataroom/manifest.json` with stable source IDs, local paths, processing status, and inclusion rationale. Structured facts such as revenue, EBITDA, debt, charges, directors, and ownership are stored separately from unstructured text so the assistant can answer deterministic questions without relying on model memory.

The FastAPI backend exposes `/health`, `/sources`, `/sources/{source_id}`, `/ask`, and eval endpoints. `/ask` classifies the question, routes financial/legal/ownership/management questions to structured data first, and uses retrieval plus optional server-side OpenAI synthesis for narrative questions. The Next.js frontend provides a chat interface, suggested diligence questions, loading/error states, and source cards so answers are inspectable.

## Accuracy Decisions

Financial figures are treated as evidence-backed facts, not generated prose. Revenue, EBITDA, and debt must come from structured records with period end, currency, unit, reported-or-computed status, formula where applicable, source ID, page/snippet evidence, extraction confidence, and review status. EBITDA is reported if present; otherwise it is computed only when every formula component is available. If the dataroom does not support an answer, the assistant should say so and list missing information.

The assistant also uses citation and verifier checks: substantive answers need source IDs from the manifest, numeric claims must be supported by structured facts or charge records, and narrative synthesis receives only retrieved evidence. This keeps the demo credible for lender-style questions where exactness matters.

## Deployment

The app is split for simple deployment. The backend can run on a Python host with `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, using SQLite for a demo or Postgres once persistence/multi-instance requirements justify it. The frontend can run on Vercel, Netlify, or any Node host with `npm run build` and `npm run start`. `OPENAI_API_KEY` is backend-only; the frontend only receives `NEXT_PUBLIC_API_BASE_URL`.

## Future Work

- Better OCR and table extraction for Companies House PDFs.
- A human review queue for extracted financial values before they become answerable facts.
- Scheduled Companies House refresh with manifest diffs and stale-source alerts.
- Full audit trail from source document to chunk, extraction, review, answer, and citation.
- Authentication and access control for non-public demos or client-specific datarooms.
- Expanded lender risk model covering covenants, liquidity, security package, operational risks, and store expansion sensitivity.
