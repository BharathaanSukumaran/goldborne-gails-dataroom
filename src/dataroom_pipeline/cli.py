from __future__ import annotations

import argparse
import json

from .paths import DB_PATH, MANIFEST_PATH
from .pipeline import run_pipeline
from .models import validate_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the dataroom pipeline")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("run", help="Run the full pipeline")
    subparsers.add_parser("validate", help="Validate the source manifest")
    args = parser.parse_args()

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
