from __future__ import annotations

import argparse
import json

from .paths import DB_PATH, MANIFEST_PATH
from .pipeline import run_pipeline
from .models import validate_manifest
from .assistant import answer_question
from .llm_client import provider_status


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the dataroom pipeline")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("run", help="Run the full pipeline")
    subparsers.add_parser("validate", help="Validate the source manifest")
    ask_parser = subparsers.add_parser("ask", help="Ask the dataroom assistant")
    ask_parser.add_argument("question", help="Question to ask")
    subparsers.add_parser("llm-status", help="Show LLM/provider configuration status")
    args = parser.parse_args()

    if args.command == "llm-status":
        print(json.dumps(provider_status(), indent=2))
        return

    if args.command == "ask":
        print(json.dumps(answer_question(args.question), indent=2))
        return

    if args.command == "validate":
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        issues = validate_manifest(manifest)
        print(json.dumps([issue.__dict__ for issue in issues], indent=2))
        if any(issue.severity == "error" for issue in issues):
            raise SystemExit(1)
        return

    result = run_pipeline()
    print(f"Wrote {DB_PATH}")
    print(f"Documents: {len(result['documents'])}")
    print(f"Issues: {len(result['issues'])}")


if __name__ == "__main__":
    main()
