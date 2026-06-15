# Goldborne Capital GAIL'S Dataroom

Public-source AI dataroom assistant for Goldborne Capital's GAIL'S LIMITED case study. The app ingests Companies House and curated public-source material, registers sources in a manifest, exposes a chat-first diligence UI, and answers only from structured facts or cited retrieved evidence.

Live demo: https://goldborne-gails-dataroom.netlify.app

Current honesty check: the dataroom has source coverage and structured answer paths, but it currently has `0` reviewed usable financial facts. Revenue, EBITDA, debt, cash, and profit figures must therefore return unavailable until source-account extraction and human review are completed.

## What The App Does

- Answers diligence questions for GAIL'S LIMITED, company number `06055393`.
- Uses `dataroom/manifest.json` as the source registry for public filings and curated public context.
- Routes exact financial questions through reviewed structured facts before any narrative synthesis.
- Routes charges, ownership, and management questions through structured records and cited sources.
- Uses manifest-backed retrieval for narrative questions such as business, ownership, and credit context.
- Uses OpenAI server-side only, when configured, for grounded synthesis over retrieved evidence.
- Refuses unsupported questions and missing financial values instead of inventing numbers.

## Repository Layout

- `dataroom/` - source manifest, raw Companies House files, processed snippets, processing error records, and coverage metadata.
- `backend/` - FastAPI API, SQLite/JSON structured facts, retrieval and verifier logic, pytest tests, and eval cases.
- `frontend/` - Next.js chatbot UI, source drawer, reviewed facts view, and frontend smoke tests.
- `netlify/functions/` - Netlify API functions for deployed `/api/health`, `/api/sources`, and `/api/ask`.
- `scripts/` - ingestion, processing, extraction, review, eval, submission-check, and production-verification scripts.
- `writeup.md` - short technical submission writeup.

## Architecture

```text
Browser UI
-> Netlify API function or FastAPI endpoint
-> question classifier
-> structured facts first for financials / charges / ownership
-> manifest-backed retrieval for narrative answers
-> OpenAI Responses API server-side synthesis when enabled
-> verifier
-> cited answer or unavailable response
```

The frontend does not call OpenAI directly and must not receive `OPENAI_API_KEY`. Browser-visible configuration is limited to values such as `NEXT_PUBLIC_API_BASE_URL`.

## Ingestion Pipeline

The pipeline is intentionally small but real:

1. `scripts/ingest_companies_house.py` refreshes Companies House profile and filing-history metadata for `06055393`, identifies the latest three relevant parent accounts filings, stores raw files under `dataroom/raw/companies_house/`, and updates `dataroom/manifest.json`.
2. `scripts/process_documents.py` converts local documents into page-level processed text where possible, writes processed files under `dataroom/processed/`, and creates explicit `.processing_error.json` records when parsing fails.
3. `scripts/extract_financials.py` scans processed account text for candidate metrics and writes `backend/data/financial_facts.json`.
4. `scripts/review_financial_facts.py` lists candidates and promotes only explicitly approved facts by setting both `reviewed: true` and `usedInAnswers: true`.
5. `scripts/build_dataroom.py` runs ingest, process, extract, and validation, then prints source/fact coverage.

Current pipeline state: the three parent consolidated accounts for 2025, 2024, and 2023 are registered, but their processing status is `processing_failed` because usable account text/table extraction is not yet available. `backend/data/financial_facts.json` contains unreviewed placeholder/candidate records with no extracted values, so there are `0` extracted candidate values and `0` reviewed usable financial facts.

## Run The Pipeline

Use the normal pipeline command when missing reviewed financial facts should fail the build:

```bash
python3 scripts/build_dataroom.py
```

For the current submission/demo state, where missing revenue, EBITDA, and debt are expected and must remain unavailable, run:

```bash
python3 scripts/build_dataroom.py --allow-missing-critical
```

Run individual steps when debugging:

```bash
python3 scripts/ingest_companies_house.py
python3 scripts/process_documents.py --process --update-manifest
python3 scripts/extract_financials.py
python3 scripts/process_documents.py --update-manifest
```

## Reviewed Financial Facts

Financial values are never trusted from model output. A financial fact can be used in an answer only when both gates are true:

- `reviewed: true` - a human checked the metric, period, value, source, page, and quote against the original source.
- `usedInAnswers: true` - the reviewed fact is approved for final answer generation.

List pending candidate facts:

```bash
python3 scripts/review_financial_facts.py --list-pending
```

Promote explicitly reviewed facts with a decision file:

```json
{
  "approved": [
    {
      "workspaceId": "gails-limited",
      "periodEnd": "2025-02-28",
      "metric": "revenue",
      "sourceId": "ch-parent-accounts-2025"
    }
  ]
}
```

```bash
python3 scripts/review_financial_facts.py review-decisions.json
```

The review script does not auto-approve facts. It also rejects approvals without a value, page, and quote.

## Why Financial Values Are Unavailable

The public dataroom currently lacks reviewed, answer-approved financial facts. The latest parent accounts are present in the manifest, but the PDF text/table extraction has not produced usable reviewed values. Because of that:

- revenue/turnover is unavailable;
- EBITDA is unavailable unless directly reviewed or computable from reviewed operating profit, depreciation, and amortisation for the same period;
- debt/borrowings is unavailable;
- covenant headroom and private facility terms are unavailable in the public dataroom.

This is expected behavior. The assistant should say the values are unavailable and list the missing reviewed facts rather than approximate figures from memory or model synthesis.

## Local Setup

Prerequisites:

- Python 3.11+
- Node.js 20+
- OpenAI API key only if enabling server-side narrative synthesis

Create environment files:

```bash
cp .env.example .env
cp .env.example frontend/.env.local
```

Install backend dependencies:

```bash
cd backend
python3 -m venv .venv
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

Open `http://localhost:3000`. The frontend defaults to the local backend through `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` when configured, or `/api` in the Netlify deployment path.

Useful API checks:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/sources
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What charges are registered against the company and who holds them?"}'
```

## OpenAI Use

OpenAI is optional and server-side:

- FastAPI and Netlify functions read `process.env.OPENAI_API_KEY`.
- `USE_OPENAI_SYNTHESIS=true` enables model-backed narrative synthesis.
- `OPENAI_MODEL` selects the synthesis model.
- If the key is missing or synthesis is disabled, the API returns a deterministic retrieved-snippet fallback or a clear unavailable/configuration response.
- Exact financial figures, lenders, directors, ownership, charges, and dates must be supported by structured facts or retrieved citations.

Do not set `OPENAI_API_KEY` in `frontend/.env.local`, do not prefix it with `NEXT_PUBLIC_`, and do not call OpenAI from browser code.

## Environment Variables

Backend / Netlify server variables:

```text
DATABASE_URL=sqlite:///./dataroom.sqlite
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
USE_OPENAI_SYNTHESIS=true
```

Frontend variable:

```text
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Leave `NEXT_PUBLIC_API_BASE_URL` unset on Netlify when the deployed frontend should call bundled Netlify functions at `/api`. Set it only when pointing the frontend at a separately hosted FastAPI backend.

## Local Tests And Submission Check

Run the complete local gate:

```bash
python3 scripts/test_submission.py
```

Equivalent wrapper:

```bash
scripts/run_local_smoke.sh
```

The submission check runs backend pytest, offline evals, frontend lint, frontend build, frontend smoke tests, raw-label scan, secret scan, and manifest validation. It prints `SUBMISSION CHECK: PASS` or `SUBMISSION CHECK: FAIL`.

Run backend tests:

```bash
cd backend
source .venv/bin/activate
pytest
```

Run answer-quality evals:

```bash
python3 scripts/run_evals.py --responses backend/app/evals/sample_responses.json
python3 scripts/run_evals.py --base-url http://127.0.0.1:8000
```

Run frontend checks:

```bash
cd frontend
npm run lint
npm run build
npm run test
```

## Netlify Deployment

The repository includes `netlify.toml` for a root Netlify deploy. Netlify installs root dependencies for `netlify/functions`, installs the frontend, then builds the Next.js app from `frontend/`.

Build settings:

```text
Base directory: .
Build command: npm install --no-package-lock && npm --prefix frontend ci && npm --prefix frontend run build
Publish directory: frontend/.next
Functions directory: netlify/functions
```

Set server-only Netlify environment variables when enabling synthesis:

```text
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
USE_OPENAI_SYNTHESIS=true
```

Optional:

```text
NEXT_PUBLIC_API_BASE_URL=
```

Keep `NEXT_PUBLIC_API_BASE_URL` empty for bundled Netlify functions. Use a full backend URL only for a separate backend deployment.

## Production Verification

After deploying, run:

```bash
scripts/verify_production.sh https://goldborne-gails-dataroom.netlify.app
```

The script checks the homepage, `/api/health`, `/api/sources`, normal `/api/ask`, unavailable financial answers, unavailable covenant/private-term answers, citations where evidence exists, and stale UI symptoms such as old copy or `0 indexed sources`.

## Deployment Checklist

- The homepage shows Goldborne Capital and GAIL'S Limited.
- `/api/health` returns ok.
- `/api/sources` returns nonzero sources and indexed sources.
- `/api/ask` returns cited evidence where the dataroom supports the answer.
- Financial questions with no reviewed usable facts return unavailable and do not include invented numbers.
- `OPENAI_API_KEY` exists only in backend/Netlify server environment variables.
- `USE_OPENAI_SYNTHESIS` is intentionally set for the deployment mode.
- `.env` and `frontend/.env.local` are not committed.
- Production verification passes after deploy.

## Known Limitations

- The latest three parent consolidated accounts are registered, but PDF processing currently fails into explicit processing-error records.
- There are currently `0` reviewed usable financial facts, so exact revenue, EBITDA, debt, cash, and profit answers are unavailable.
- Curated public-news sources are intentionally lightweight and should be expanded with licensing-safe excerpts before broader use.
- The review workflow is CLI-based rather than a full human review UI.
- OpenAI synthesis is optional; without server-side configuration, narrative answers fall back to deterministic retrieval or unavailable responses.
- SQLite is suitable for local/demo use; a managed database is preferable for long-lived multi-user production.

## Future Work

- Improve OCR and table extraction for Companies House PDFs.
- Add a reviewer UI with audit trail from source page to approved fact to final answer.
- Schedule Companies House refreshes with manifest diffs and stale-source alerts.
- Expand public source coverage beyond Companies House and curated notes.
- Add authentication and access control for non-public datarooms.
- Broaden credit analysis to covenants, liquidity, security package, operating risks, and sensitivity analysis once supported sources are available.
