# Goldborne Capital Intelligence Platform

AI-powered company intelligence, credit analysis, and dataroom interrogation platform for Goldborne Capital. GAIL'S LIMITED / Gail's Bakery, company number `06055393`, is the initial selected workspace and case study.

Live demo: https://goldborne-gails-dataroom.netlify.app

The project combines a curated public dataroom, a FastAPI backend, Netlify serverless API functions, and a Next.js frontend. The platform answers credit and diligence questions with citations, routes exact financial/legal questions through structured facts, and says when the workspace dataroom does not contain enough evidence.

## Repository Layout

- `dataroom/` - manifest, source notes, raw source placeholders, processed notes, and coverage metadata.
- `backend/` - FastAPI API, SQLite-backed structured facts, retrieval/QA helpers, and pytest tests.
- `frontend/` - Next.js chat UI and source browser.
- `scripts/` - ingestion and extraction scripts for Companies House, document processing, and financial facts.
- `writeup.md` - one-page technical writeup and future work.

## Local Setup

Prerequisites:

- Python 3.11+
- Node.js 20+
- An OpenAI API key only if enabling narrative synthesis

Create environment files:

```bash
cp .env.example .env
cp .env.example frontend/.env.local
```

Install backend dependencies:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install frontend dependencies:

```bash
cd frontend
npm install
```

Run the backend:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run the frontend in a second terminal:

```bash
cd frontend
npm run dev
```

Open `http://localhost:3000`. The frontend calls the backend at `NEXT_PUBLIC_API_BASE_URL`, which defaults to `http://localhost:8000`.

Useful API checks:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/sources
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What charges are registered against the company and who holds them?"}'
```

Run backend tests:

```bash
cd backend
source .venv/bin/activate
pytest
```

Run answer-quality evals:

```bash
python scripts/run_evals.py --responses backend/app/evals/sample_responses.json
```

For live backend evals, start the backend and run:

```bash
python scripts/run_evals.py --base-url http://127.0.0.1:8000
```

Run frontend checks:

```bash
cd frontend
npm run lint
npm run build
```


## Environment Variables

Backend variables:

- `DATABASE_URL` - database connection string. Defaults to a local SQLite file. Use SQLite for local/demo, or a managed Postgres URL for production once the backend DB layer is configured for it.
- `OPENAI_API_KEY` - server-side OpenAI key. Leave blank to disable model synthesis.
- `OPENAI_MODEL` - model for narrative synthesis. Defaults to a small cost-effective model.
- `USE_OPENAI_SYNTHESIS` - set to `true` to allow server-side OpenAI narrative synthesis. Keep `false` for deterministic local testing.

Frontend variables:

- `NEXT_PUBLIC_API_BASE_URL` - public URL of the FastAPI backend. This is safe to expose because it is only an API base URL, not a secret.

Security notes:

- Do not put `OPENAI_API_KEY` or private credentials in frontend environment variables.
- Do not commit `.env` or `frontend/.env.local`.
- The public frontend must never call OpenAI directly; all AI calls belong behind the backend.

## Architecture

Text diagram:

```text
Browser UI -> /api/ask or FastAPI /ask -> question routing
  -> structured facts for financials / charges / ownership
  -> manifest-backed snippet retrieval for narrative questions
  -> server-side OpenAI Responses API synthesis when OPENAI_API_KEY is set
  -> verifier -> cited answer / unknown response
```

The app uses a two-track answering flow.

Structured questions are classified by topic and answered from typed facts:

- Financial questions use exact stored facts for revenue, EBITDA, debt, period end, units, source page, quote, and review status.
- Charges questions use registered charge records, status, dates, and persons entitled.
- Ownership and management questions use PSC and officer/director records.

Narrative questions use retrieval over manifest-backed dataroom text snippets and, when enabled, server-side OpenAI Responses API synthesis through the official OpenAI SDK in Netlify functions or the FastAPI backend. The model receives only selected evidence and is instructed not to invent figures, dates, lenders, ownership, or charges.

The frontend is intentionally thin: it renders the Goldborne platform shell, selected workspace, suggested prompts, source browser, and chat UI. It sends `POST /api/ask` on Netlify or `POST /ask` to FastAPI, displays confidence and missing information, and shows citations/source snippets. It only needs `NEXT_PUBLIC_API_BASE_URL` when using a separate backend.

## Dataroom Sources

`dataroom/manifest.json` is the source registry. The current workspace has 12 registered sources, of which 9 are indexed through curated Markdown snippets under `dataroom/processed/`. `/api/sources` reports `source_count`, `indexed_source_count`, categories, and enriched source metadata. The UI source browser reads this endpoint, so the workspace shows visible indexed sources instead of a static zero-source state.

The latest three Companies House parent consolidated accounts PDFs are downloaded under `dataroom/raw/companies_house/` and registered as `downloaded`/`pending`. They are intentionally not answerable financial sources yet: OCR/table extraction and human source-page review are still pending, so revenue, EBITDA, and debt remain unavailable from reviewed facts.

## Accuracy Approach

Financial and legal facts are not left to generative output. Exact values are extracted into structured records with source IDs, page/snippet evidence, and review metadata. The assistant should:

- prefer structured facts for revenue, EBITDA, debt, charges, directors, and ownership;
- compute EBITDA only when every required component is present and cite the formula;
- mark EBITDA as reported, computed, or unknown;
- block or downgrade answers with unsupported numeric claims;
- return an unknown answer when evidence is absent instead of filling gaps;
- cite every substantive answer with manifest-backed source IDs.

The current dataroom manifest also records processing status. Pending sources should not be treated as verified until raw files are downloaded, parsed, and reviewed.

### Financial Fact Review Gate

Financial facts may be stored for review even when they are not safe to answer from. Exact financial answers must only use facts where both gates are true:

- `reviewed: true` means a human checked the extracted value, period, metric, source page, and quote against the original source.
- `usedInAnswers: true` in JSON, or `used_in_answers: true` in SQLite or CSV, means the reviewed fact is approved for final answer generation.

Leave either flag false for OCR output, parser output, placeholders, incomplete EBITDA components, or values awaiting source-page review. Unreviewed facts can still be displayed in review and admin surfaces, but they must not appear in `facts_used`, citations, or exact final financial answers. EBITDA may only be reported directly from a usable EBITDA fact or computed from complete usable operating profit, depreciation, and amortisation facts.


## Backend Deployment

One practical deployment path is Render, Fly.io, Railway, or another container/Python host.

Backend steps:

1. Create a backend service rooted at `backend/`.
2. Install with `pip install -r requirements.txt`.
3. Start with:

```bash
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

4. Set production environment variables:

```text
DATABASE_URL=sqlite:////data/dataroom.sqlite
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
USE_OPENAI_SYNTHESIS=true
```

5. Persist the SQLite volume if using SQLite. For multi-instance or long-lived production, move structured facts to Postgres and set `DATABASE_URL` accordingly.
6. Confirm `GET /health`, `GET /sources`, and a known `POST /ask` request before pointing the frontend at the service.

## Netlify Deployment

The repository includes `netlify.toml` for a root Netlify deploy. Netlify installs root dependencies for `netlify/functions`, installs the frontend with `npm ci`, then builds the Next.js app from `frontend/`.

The prior production mismatch was caused by Netlify serving an older frontend-oriented deployment instead of the root deployment described here. That stale deployment did not bundle the current Netlify functions and dataroom artifacts, so the live UI showed the old product copy and a zero-indexed-source state even though the repository contained the Goldborne UI and 12-source manifest.

Netlify build settings:

```text
Base directory: .
Build command: npm install --no-package-lock && npm --prefix frontend ci && npm --prefix frontend run build
Publish directory: frontend/.next
Functions directory: netlify/functions
```

Set these Netlify environment variables when enabling model-backed synthesis:

```text
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
USE_OPENAI_SYNTHESIS=true
```

These OpenAI variables are server-only deployment secrets for Netlify functions or the FastAPI backend. Do not expose them with `NEXT_PUBLIC_*` names or place them in browser-readable frontend env files.

If the deployed UI should call the bundled Netlify functions, leave `NEXT_PUBLIC_API_BASE_URL` unset so it defaults to `/api`. Set it only when pointing the frontend at a separate backend service. Confirm the deployed UI can load `/api/sources` and submit `/api/ask` questions.

Run the production verification script after deployment:

```bash
scripts/verify_production.sh https://goldborne-gails-dataroom.netlify.app
```

The script fetches the deployed page and `/api/sources`, fails if the stale `0 indexed sources` UI is still present, and checks for at least 12 sources and 9 indexed sources.

If the frontend and backend are on different domains, configure backend CORS for the frontend origin before production use.

## Dataroom Refresh

The manifest is the source registry. Add or refresh documents by updating `dataroom/manifest.json`, placing raw files under `dataroom/raw/`, and running processing/extraction scripts. Only promote a source to `verified` after source text and extracted facts have been checked against the original filing or article notes.

## Deployment Checklist

- Backend health check returns `{"status":"ok"}`.
- Netlify root dependencies install before function bundling.
- Frontend `NEXT_PUBLIC_API_BASE_URL` is unset for bundled Netlify functions or points to the deployed backend.
- `OPENAI_MODEL` is set with `OPENAI_API_KEY` when OpenAI synthesis is enabled.
- `OPENAI_API_KEY` exists only on the backend host.
- `.env` files are not committed.
- Dataroom raw/processed files needed for demo questions are present.
- Demo questions return citations or clear missing-information messages.
- Financial values used in answers are reviewed structured facts, not model guesses.

## Known Limitations

- The latest three Companies House accounts PDFs have been downloaded but still require OCR/table extraction and human review before they can support exact financial answers.
- Revenue, EBITDA, and debt remain unavailable until those source accounts are reviewed and approved through the reviewed-facts gate.
- Without `OPENAI_API_KEY`, Netlify narrative synthesis falls back to retrieved snippets or returns a low-confidence unknown response.
- Root npm install currently reports audit advisories in Netlify dependency transitive packages; no force upgrade was applied.

## Future Improvements

- Full PDF download, OCR, and table extraction for Companies House filings.
- Human review queue for promoted financial facts.
- Workspace selector backed by multiple companies.
- Authenticated client workspaces and access control.
