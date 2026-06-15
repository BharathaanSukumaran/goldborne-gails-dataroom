#!/usr/bin/env python3
"""Run the local dataroom ingestion pipeline and print a submission summary."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "dataroom" / "manifest.json"
FACTS_PATH = ROOT / "backend" / "data" / "financial_facts.json"
REPORT_PATH = ROOT / "dataroom" / "processed" / "source_coverage_report.json"

CRITICAL_METRICS = ["revenue", "ebitda", "debt"]


def run_step(name: str, args: list[str]) -> None:
    print(f"\n== {name} ==")
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_summary() -> dict[str, Any]:
    manifest = load_json(MANIFEST_PATH)
    facts_payload = load_json(FACTS_PATH)
    report = load_json(REPORT_PATH)
    sources = manifest.get("sources", [])
    facts = facts_payload.get("facts", facts_payload if isinstance(facts_payload, list) else [])
    processed_sources = [source for source in sources if source.get("processing_status") in {"processed", "verified"}]
    failed_sources = [source for source in sources if source.get("processing_status") in {"failed", "processing_failed"}]
    extracted_candidates = [fact for fact in facts if fact.get("value") not in {None, ""}]
    reviewed_usable = [fact for fact in facts if fact.get("reviewed") is True and fact.get("usedInAnswers") is True]
    usable_metrics = {str(fact.get("metric")).lower() for fact in reviewed_usable}
    missing_critical = [metric for metric in CRITICAL_METRICS if metric not in usable_metrics]
    return {
        "total_sources": len(sources),
        "processed_sources": len(processed_sources),
        "failed_sources": len(failed_sources),
        "extracted_candidate_facts": len(extracted_candidates),
        "reviewed_usable_facts": len(reviewed_usable),
        "missing_critical_facts": missing_critical,
        "required_categories_missing": report.get("required_categories_missing", []),
    }


def print_summary(summary: dict[str, Any]) -> None:
    print("\n== Dataroom build summary ==")
    print(f"Total sources: {summary['total_sources']}")
    print(f"Processed sources: {summary['processed_sources']}")
    print(f"Failed sources: {summary['failed_sources']}")
    print(f"Extracted candidate facts: {summary['extracted_candidate_facts']}")
    print(f"Reviewed usable facts: {summary['reviewed_usable_facts']}")
    missing = summary["missing_critical_facts"]
    print(f"Missing critical facts: {', '.join(missing) if missing else 'none'}")
    categories = summary["required_categories_missing"]
    print(f"Missing source categories: {', '.join(categories) if categories else 'none'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-missing-critical", action="store_true", help="Return zero even when reviewed revenue/EBITDA/debt facts are unavailable.")
    args = parser.parse_args()

    run_step("Refresh Companies House manifest", ["scripts/ingest_companies_house.py"])
    run_step("Process local documents", ["scripts/process_documents.py", "--process", "--update-manifest"])
    run_step("Extract candidate financial facts", ["scripts/extract_financials.py"])
    run_step("Validate source coverage", ["scripts/process_documents.py", "--update-manifest"])

    summary = build_summary()
    print_summary(summary)
    critical_failures = list(summary["required_categories_missing"])
    if summary["missing_critical_facts"]:
        critical_failures.append("reviewed usable financial facts missing: " + ", ".join(summary["missing_critical_facts"]))

    if critical_failures and not args.allow_missing_critical:
        print("\nCritical build failure:")
        for failure in critical_failures:
            print(f"- {failure}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
