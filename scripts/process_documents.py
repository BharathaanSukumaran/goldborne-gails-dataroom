#!/usr/bin/env python3
"""Validate source coverage and local raw-file readiness for the dataroom."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "dataroom" / "manifest.json"
DEFAULT_REPORT = ROOT / "dataroom" / "processed" / "source_coverage_report.json"


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def source_state(source: dict[str, Any], root: Path) -> dict[str, Any]:
    local_path = root / source["local_path"]
    exists = local_path.exists()
    status = source["processing_status"]
    issue = None
    if status in {"pending_download", "pending_manual_curation"} and not exists:
        issue = "expected raw source is not present yet"
    elif status in {"downloaded", "processed", "verified"} and not exists:
        issue = "manifest status claims local availability but file is missing"

    return {
        "source_id": source["source_id"],
        "category": source["category"],
        "title": source["title"],
        "processing_status": status,
        "local_path": source["local_path"],
        "local_exists": exists,
        "issue": issue,
    }


def build_report(manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    states = [source_state(source, root) for source in manifest["sources"]]
    category_counts = Counter(source["category"] for source in manifest["sources"])
    status_counts = Counter(source["processing_status"] for source in manifest["sources"])
    required = set(manifest["coverage"]["required_categories"])
    covered = set(category_counts)
    missing = sorted(required - covered)

    latest_accounts = [
        {
            "source_id": source["source_id"],
            "period_end": source.get("period_end"),
            "filed_at": source.get("filed_at"),
            "pages": source.get("pages"),
            "processing_status": source["processing_status"],
        }
        for source in manifest["sources"]
        if source["category"] == "accounts"
    ]

    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "company": manifest["company"],
        "source_count": len(manifest["sources"]),
        "category_counts": dict(sorted(category_counts.items())),
        "processing_status_counts": dict(sorted(status_counts.items())),
        "required_categories_missing": missing,
        "latest_three_accounts": sorted(latest_accounts, key=lambda item: item["period_end"], reverse=True),
        "companies_house_sources": [
            state["source_id"]
            for state in states
            if state["category"] != "news"
        ],
        "curated_news_placeholders": [
            state["source_id"]
            for state in states
            if state["category"] == "news"
        ],
        "issues": [state for state in states if state["issue"]],
        "sources": states,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    report = build_report(manifest, ROOT)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {args.output}")
    print(f"Sources: {report['source_count']}")
    print(f"Missing required categories: {', '.join(report['required_categories_missing']) or 'none'}")
    print(f"Issues: {len(report['issues'])}")


if __name__ == "__main__":
    main()
