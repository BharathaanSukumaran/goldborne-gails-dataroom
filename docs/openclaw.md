# OpenClaw Local Control Plane

OpenClaw is a local/admin development and QA control plane for this dataroom assistant. It is useful for running setup checks, driving local endpoint smoke tests, and coordinating ingestion or answer-quality review during development.

The public app must not depend on OpenClaw. The deployed browser UI should call the deployed FastAPI backend directly, and the backend should run without a local OpenClaw gateway, daemon, workspace, or agent session.

## Allowed Use

- Local development orchestration for backend, frontend, ingestion, and eval tasks.
- Admin-only QA checks against a local or private staging backend.
- Manual smoke tests of `/health`, `/ask`, and `/evals/run`.
- Local review workflows that never expose private direct messages, personal accounts, or unrelated workspace data.

## Not Allowed

- Do not make the public frontend call OpenClaw.
- Do not require OpenClaw to start the backend or serve the deployed app.
- Do not put OpenClaw workspace URLs, tokens, or local gateway assumptions into production config.
- Do not commit provider API keys, OpenClaw credentials, `.env`, run logs with secrets, or raw prompts/responses containing confidential data.

## Safe Setup Notes

1. Use a local/admin workspace only. Keep personal chats, public DMs, and unrelated company data out of the workspace context.
2. Keep provider keys server-side. `OPENAI_API_KEY` belongs in a local `.env` file or deployment secret store, never in frontend code or committed files.
3. Run OpenClaw doctor/check commands before using it for QA. Use the command names provided by your local OpenClaw install, for example:

```bash
openclaw doctor
openclaw check
```

4. Confirm the app itself starts independently of OpenClaw:

```bash
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

5. Keep local logs minimal. If logs are needed for debugging, redact `Authorization`, `OPENAI_API_KEY`, provider tokens, cookies, and customer data before sharing.

## Local Endpoint Smoke Tests

These examples assume the FastAPI backend is running on `http://127.0.0.1:8000`. They can be run directly from a shell, from an OpenClaw local command, or from any admin-only QA harness.

### Health

```bash
curl -sS http://127.0.0.1:8000/health
```

Expected shape:

```json
{"status":"ok","app":"..."}
```

### Ask

```bash
curl -sS http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"What was revenue and EBITDA in the last reported year?"}'
```

Check that the response includes:

- `answer`
- `answer_type`
- `citations`
- `facts_used` for structured financial answers
- `missing_information` when the dataroom cannot support an answer

### Evals

```bash
curl -sS http://127.0.0.1:8000/evals/run \
  -H 'Content-Type: application/json' \
  -d '{"questions":["What charges are registered against the company and who holds them?","What are the key risks for a lender?"]}'
```

Check that the response includes `total`, `passed`, `failed`, and per-question results. Failed evals should be treated as a QA signal, not hidden by OpenClaw automation.

## API Key Safety

- Store `OPENAI_API_KEY` only in `.env`, CI/deployment secrets, or a local secret manager.
- Never prefix frontend environment variables with secret provider keys. In Next.js, anything exposed as `NEXT_PUBLIC_*` is client-visible.
- Do not paste live keys into OpenClaw prompts, task descriptions, logs, or shared transcripts.
- Rotate any key that appears in a committed file, public terminal output, issue, PR, or screenshot.

## Dependency Boundary

OpenClaw may drive local checks, but it is outside the runtime architecture:

```text
Browser UI -> FastAPI backend -> structured facts / retrieval / OpenAI server-side calls
```

There should be no production path like:

```text
Browser UI -> OpenClaw -> FastAPI backend
```

This boundary keeps the deployed app simple, reproducible, and independent of local/admin control-plane tooling.
