---
name: gails-dataroom
description: Query and operate the Gail's Limited dataroom pipeline and assistant from this workspace.
---

Use this skill when the user asks about the Gail's Limited dataroom, company number 06055393, the pipeline, source coverage, charges, ownership, management, credit risks, or the assistant demo.

The workspace root is `{baseDir}/../..` when this skill is installed in the project `skills/` directory. Prefer running commands from that repository root.

Key commands:

```bash
python -m dataroom_pipeline.cli run
python -m dataroom_pipeline.cli validate
python -m dataroom_pipeline.cli llm-status
python -m dataroom_pipeline.cli ask "What charges are registered against the company?"
```

Operational rules:

- Treat `data/source_manifest.json` as the document source of truth.
- Treat `data/normalized/dataroom.sqlite` as the canonical structured store.
- Use structured answers for financial facts, charges, officers, and ownership.
- Do not invent missing revenue, EBITDA, or debt values; report that the source PDF still needs verification when the fact is unavailable.
- Mention source documents and URLs from the assistant output when answering.
- If asked about UI, direct the user to the Streamlit workspace with Overview, Pipeline, Assistant, and Documents tabs.
