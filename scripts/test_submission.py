#!/usr/bin/env python3
"""Run the complete pre-submission quality gate."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "dataroom" / "manifest.json"
MANIFEST_SCHEMA_PATH = ROOT / "dataroom" / "manifest.schema.json"
SAMPLE_RESPONSES_PATH = ROOT / "backend" / "app" / "evals" / "sample_responses.json"
GOLDEN_CASES_PATH = ROOT / "backend" / "app" / "evals" / "golden_cases.json"

RAW_LABEL_SCRIPT = ROOT / "scripts" / "check_frontend_display_labels.mjs"
BACKEND_PYTHON = ROOT / "backend" / ".venv" / "bin" / "python"
PYTHON = str(BACKEND_PYTHON if BACKEND_PYTHON.exists() else Path(sys.executable))
SECRET_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b")

SOURCE_REQUIRED_FIELDS = {
    "source_id",
    "title",
    "category",
    "issuer",
    "retrieved_at",
    "source_url",
    "local_path",
    "included_reason",
    "processing_status",
    "source_status",
}
VALID_CATEGORIES = {
    "company_profile",
    "filing_history",
    "accounts",
    "charges",
    "management",
    "ownership",
    "news",
}
VALID_PROCESSING_STATUSES = {
    "pending_download",
    "pending_manual_curation",
    "downloaded",
    "processed",
    "verified",
    "pending_review",
    "failed",
    "processing_failed",
}
VALID_SOURCE_STATUSES = {"pending", "processed", "verified"}
REQUIRED_CHARGE_EVAL_CASE_IDS = {
    "charge_holder_0006",
    "charge_status_0005",
    "charge_description_reviewed_summary",
    "secured_assets_reviewed_summary",
    "charge_created_date_0006",
    "charge_year_resolution_2021",
    "no_generic_answer_for_specific_charge_field",
    "what_is_charge_for_reviewed_summary",
}

CHECK_COMMANDS: dict[str, list[str]] = {
    "backend pytest": [PYTHON, "-m", "pytest", "backend/tests"],
    "offline evals": [
        PYTHON,
        "scripts/run_evals.py",
        "--responses",
        str(SAMPLE_RESPONSES_PATH.relative_to(ROOT)),
    ],
    "frontend lint": ["npm", "--prefix", "frontend", "run", "lint"],
    "frontend build": ["npm", "--prefix", "frontend", "run", "build"],
    "frontend test": ["npm", "--prefix", "frontend", "run", "test"],
    "raw-label scan": ["node", str(RAW_LABEL_SCRIPT.relative_to(ROOT))],
    "dataroom pipeline": [PYTHON, "scripts/build_dataroom.py", "--allow-missing-critical"],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="append",
        choices=[
            *CHECK_COMMANDS.keys(),
            "manifest validation",
            "secret scan",
            "charge eval coverage",
        ],
        help="Run only the named check. May be provided more than once.",
    )
    args = parser.parse_args()

    selected = set(args.check or [])
    failures: list[str] = []

    for name, command in CHECK_COMMANDS.items():
        if selected and name not in selected:
            continue
        failure = run_command(name, command)
        if failure:
            failures.append(failure)

    if not selected or "manifest validation" in selected:
        failures.extend(run_python_check("manifest validation", validate_manifest))

    if not selected or "charge eval coverage" in selected:
        failures.extend(run_python_check("charge eval coverage", validate_charge_eval_coverage))

    if not selected or "secret scan" in selected:
        failures.extend(run_python_check("secret scan", scan_for_secrets))

    if failures:
        print("SUBMISSION CHECK: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("SUBMISSION CHECK: PASS")
    return 0


def run_command(name: str, command: Sequence[str]) -> str | None:
    printable = " ".join(command)
    print(f"Running {name}: {printable}")
    result = subprocess.run(command, cwd=ROOT, text=True)
    if result.returncode:
        return f"{name} failed: command `{printable}` exited with {result.returncode}"
    return None


def run_python_check(name: str, check) -> list[str]:
    print(f"Running {name}")
    failures = check()
    if failures:
        return [f"{name} failed: {failure}" for failure in failures]
    return []


def validate_manifest() -> list[str]:
    failures: list[str] = []
    if not MANIFEST_SCHEMA_PATH.exists():
        failures.append(f"missing schema at {relative(MANIFEST_SCHEMA_PATH)}")
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - report parse and file errors uniformly.
        return [f"could not read {relative(MANIFEST_PATH)}: {exc}"]

    for field in ["schema_version", "generated_at", "company", "coverage", "sources"]:
        if field not in manifest:
            failures.append(f"manifest missing required field {field!r}")

    if manifest.get("schema_version") != "1.0":
        failures.append("schema_version must be '1.0'")

    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        failures.append("sources must be a non-empty list")
        return failures

    source_ids = [source.get("source_id") for source in sources if isinstance(source, dict)]
    duplicate_ids = [source_id for source_id, count in Counter(source_ids).items() if count > 1]
    if duplicate_ids:
        failures.append("duplicate source_id values: " + ", ".join(sorted(duplicate_ids)))

    required_categories = set((manifest.get("coverage") or {}).get("required_categories") or [])
    covered_categories = {source.get("category") for source in sources if isinstance(source, dict)}
    missing_categories = sorted(required_categories - covered_categories)
    if missing_categories:
        failures.append("required categories missing from sources: " + ", ".join(missing_categories))

    accounts = [
        source
        for source in sources
        if isinstance(source, dict) and source.get("category") == "accounts"
    ]
    if len(accounts) < 3:
        failures.append("manifest must include at least the latest three account sources")

    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            failures.append(f"sources[{index}] must be an object")
            continue
        failures.extend(validate_source(source, index))

    return failures


def validate_source(source: dict, index: int) -> list[str]:
    failures: list[str] = []
    source_id = str(source.get("source_id") or f"sources[{index}]")
    missing_fields = sorted(SOURCE_REQUIRED_FIELDS - set(source))
    if missing_fields:
        failures.append(f"{source_id}: missing fields: {', '.join(missing_fields)}")

    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(source.get("source_id", ""))):
        failures.append(f"{source_id}: source_id must be lowercase kebab-case")
    if source.get("category") not in VALID_CATEGORIES:
        failures.append(f"{source_id}: invalid category {source.get('category')!r}")
    if source.get("processing_status") not in VALID_PROCESSING_STATUSES:
        failures.append(f"{source_id}: invalid processing_status {source.get('processing_status')!r}")
    if source.get("source_status") not in VALID_SOURCE_STATUSES:
        failures.append(f"{source_id}: invalid source_status {source.get('source_status')!r}")

    processing_status = source.get("processing_status")
    expected_source_status = source_status_for(str(processing_status))
    if source.get("source_status") != expected_source_status:
        failures.append(
            f"{source_id}: source_status {source.get('source_status')!r} does not match "
            f"processing_status {processing_status!r}"
        )

    local_path = safe_repo_path(source.get("local_path"))
    if local_path is None:
        failures.append(f"{source_id}: local_path must be a relative repo path")
    elif processing_status == "downloaded" and not local_path.exists():
        failures.append(f"{source_id}: downloaded local_path is missing: {relative(local_path)}")

    processed_path_value = source.get("processed_path")
    processed_path = safe_repo_path(processed_path_value) if processed_path_value else None
    if processed_path_value and processed_path is None:
        failures.append(f"{source_id}: processed_path must be a relative repo path")
    if processing_status in {"processed", "verified"}:
        if processed_path is None:
            failures.append(f"{source_id}: {processing_status} source needs processed_path")
        elif not processed_path.exists():
            failures.append(f"{source_id}: processed_path is missing: {relative(processed_path)}")

    return failures


def source_status_for(processing_status: str) -> str:
    if processing_status == "verified":
        return "verified"
    if processing_status == "processed":
        return "processed"
    return "pending"


def validate_charge_eval_coverage() -> list[str]:
    failures: list[str] = []
    try:
        golden = json.loads(GOLDEN_CASES_PATH.read_text(encoding="utf-8"))
        samples = json.loads(SAMPLE_RESPONSES_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - report parse and file errors uniformly.
        return [f"could not read charge eval files: {exc}"]

    case_items = golden.get("cases") if isinstance(golden, dict) else golden
    case_ids = {case.get("id") for case in case_items or [] if isinstance(case, dict)}
    sample_ids = set(samples) if isinstance(samples, dict) else set()

    missing_cases = sorted(REQUIRED_CHARGE_EVAL_CASE_IDS - case_ids)
    if missing_cases:
        failures.append("golden cases missing required charge evals: " + ", ".join(missing_cases))

    missing_samples = sorted(REQUIRED_CHARGE_EVAL_CASE_IDS - sample_ids)
    if missing_samples:
        failures.append("sample responses missing required charge evals: " + ", ".join(missing_samples))

    return failures


def safe_repo_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return None
    return ROOT / path


def scan_for_secrets() -> list[str]:
    failures: list[str] = []
    tracked_files = git_tracked_files()
    openai_key = os.environ.get("OPENAI_API_KEY", "")

    for path in tracked_files:
        if should_skip_secret_scan(path):
            continue
        absolute = ROOT / path
        try:
            text = absolute.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SECRET_RE.search(text):
            failures.append(f"{path}: contains a token matching sk-*")
        if openai_key and openai_key in text:
            failures.append(f"{path}: contains the current OPENAI_API_KEY value")

    ignored = git_ignored_paths([".env", "frontend/.env.local"])
    for required in [".env", "frontend/.env.local"]:
        if required not in ignored:
            failures.append(f"{required} must be gitignored")

    return failures


def git_tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def git_ignored_paths(paths: list[str]) -> set[str]:
    result = subprocess.run(
        ["git", "check-ignore", *paths],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return set(result.stdout.splitlines())


def should_skip_secret_scan(path: str) -> bool:
    return (
        path.endswith(".env.example")
        or path.endswith("package-lock.json")
        or path.startswith("frontend/package-lock.json")
        or path.startswith(".git/")
    )


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
