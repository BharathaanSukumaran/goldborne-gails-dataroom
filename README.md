# Goldborne Dataroom Assistant

AI dataroom assistant for GAIL'S LIMITED / Gail's Bakery, company number `06055393`.

Live demo: https://goldborne-gails-dataroom.netlify.app

The project combines a curated public dataroom, a FastAPI backend, and a Next.js frontend. The assistant is designed to answer credit and diligence questions with citations, route exact financial/legal questions through structured facts, and say when the dataroom does not contain enough evidence.

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

The app uses a two-track answering flow.

Structured questions are classified by topic and answered from typed facts:

- Financial questions use exact stored facts for revenue, EBITDA, debt, period end, units, source page, quote, and review status.
- Charges questions use registered charge records, status, dates, and persons entitled.
- Ownership and management questions use PSC and officer/director records.

Narrative questions use retrieval over dataroom text snippets and, when enabled, server-side OpenAI synthesis. The model receives only the selected evidence and is instructed not to invent figures, dates, lenders, ownership, or charges.

The frontend is intentionally thin: it renders suggested questions, sends `POST /ask`, displays confidence and missing information, and shows citations/source snippets. It only needs `NEXT_PUBLIC_API_BASE_URL`.

## Accuracy Approach

Financial and legal facts are not left to generative output. Exact values are extracted into structured records with source IDs, page/snippet evidence, and review metadata. The assistant should:

- prefer structured facts for revenue, EBITDA, debt, charges, directors, and ownership;
- compute EBITDA only when every required component is present and cite the formula;
- mark EBITDA as reported, computed, or unknown;
- block or downgrade answers with unsupported numeric claims;
- return an unknown answer when evidence is absent instead of filling gaps;
- cite every substantive answer with manifest-backed source IDs.

The current dataroom manifest also records processing status. Pending sources should not be treated as verified until raw files are downloaded, parsed, and reviewed.

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

## Frontend Deployment

Deploy the Next.js app to Vercel, Netlify, or another Node-capable host.

Frontend steps:

1. Create a frontend project rooted at `frontend/`.
2. Build with:

```bash
npm install
npm run build
```

3. Start with:

```bash
npm run start
```

4. Set:

```text
NEXT_PUBLIC_API_BASE_URL=https://your-backend.example.com
```

5. Confirm the deployed UI can load `/sources` and submit `/ask` questions.

If the frontend and backend are on different domains, configure backend CORS for the frontend origin before production use.

## Dataroom Refresh

The manifest is the source registry. Add or refresh documents by updating `dataroom/manifest.json`, placing raw files under `dataroom/raw/`, and running processing/extraction scripts. Only promote a source to `verified` after source text and extracted facts have been checked against the original filing or article notes.

## Deployment Checklist

- Backend health check returns `{"status":"ok"}`.
- Frontend `NEXT_PUBLIC_API_BASE_URL` points to the deployed backend.
- `OPENAI_API_KEY` exists only on the backend host.
- `.env` files are not committed.
- Dataroom raw/processed files needed for demo questions are present.
- Demo questions return citations or clear missing-information messages.
- Financial values used in answers are reviewed structured facts, not model guesses.
