# Interview Walkthrough

1. Ask a brief question, for example: "What was revenue and EBITDA in the last reported year?"
2. `POST /ask` receives the question and classifies it as financial, charges, ownership/management, or narrative.
3. Financial questions route to structured facts first. Revenue, EBITDA, and debt must come from reviewed database rows, using exact `Decimal`/integer storage rather than model text.
4. EBITDA is labelled as reported, computed, or unknown. If the reported value is absent, it is computed only when every required component is present.
5. Narrative questions retrieve source snippets from the dataroom and pass only cited evidence to synthesis.
6. The verifier blocks unsupported numeric claims and the final response carries `answer`, `answer_type`, `facts_used`, `citations`, `missing_information`, and `confidence`.
7. `scripts/run_evals.py` replays golden questions and checks exact-or-unknown financial behavior, source attribution, and refusal to invent private or missing facts.

Demo command:

```bash
python scripts/run_evals.py --base-url http://127.0.0.1:8000
```

Offline checker command for a saved response fixture:

```bash
python scripts/run_evals.py --responses backend/app/evals/sample_responses.json
```
