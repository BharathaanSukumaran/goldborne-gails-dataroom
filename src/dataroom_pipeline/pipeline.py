from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .extractors import extract_text
from .models import ManifestIssue, validate_manifest
from .paths import DB_PATH, INBOX_DIR, MANIFEST_PATH, PROCESSED_DIR, REPORTS_DIR, SEED_PATH
from .storage import connect, insert_document, insert_seed, reset


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_pipeline(
    manifest_path: Path = MANIFEST_PATH,
    seed_path: Path = SEED_PATH,
    db_path: Path = DB_PATH,
) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    seed = load_json(seed_path)

    manifest_issues = validate_manifest(manifest)
    if any(issue.severity == "error" for issue in manifest_issues):
        _write_report("validation_report.json", {"issues": [issue.__dict__ for issue in manifest_issues]})
        raise ValueError("Manifest validation failed; see reports/validation_report.json")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    conn = connect(db_path)
    reset(conn)

    document_inventory: list[dict[str, Any]] = []
    qa_issues: list[ManifestIssue] = []

    for doc in manifest["documents"]:
        processed_path = _process_document(doc)
        insert_document(conn, doc, str(processed_path) if processed_path else None)
        document_inventory.append(
            {
                "document_id": doc["document_id"],
                "title": doc["title"],
                "category": doc["category"],
                "source": doc["source"],
                "source_url": doc["source_url"],
                "processed": processed_path is not None,
                "expected_inbox_file": doc.get("expected_inbox_file"),
            }
        )
        if doc.get("expected_inbox_file") and processed_path is None:
            qa_issues.append(
                ManifestIssue(
                    "warning",
                    f"Expected inbox file not found: {doc['expected_inbox_file']}",
                    doc["document_id"],
                )
            )

    insert_seed(conn, seed)
    coverage_issues = _coverage_checks(manifest, seed)
    qa_issues.extend(coverage_issues)

    for issue in qa_issues:
        conn.execute(
            "INSERT INTO qa_findings (severity, finding, status, document_id) VALUES (?, ?, ?, ?)",
            (issue.severity, issue.message, "open", issue.document_id),
        )
    conn.commit()
    conn.close()

    result = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "database": str(db_path),
        "documents": document_inventory,
        "issues": [issue.__dict__ for issue in qa_issues],
    }
    _write_report("document_inventory.json", {"documents": document_inventory})
    _write_report("validation_report.json", result)
    _write_report("app_summary.json", _summary(manifest, seed, result))
    return result


def _process_document(doc: dict[str, Any]) -> Path | None:
    expected = doc.get("expected_inbox_file")
    if not expected:
        return None

    inbox_path = INBOX_DIR / expected
    if not inbox_path.exists():
        return None

    target_dir = PROCESSED_DIR / doc["document_id"]
    target_dir.mkdir(parents=True, exist_ok=True)
    copied_source = target_dir / inbox_path.name
    if inbox_path.resolve() != copied_source.resolve():
        shutil.copy2(inbox_path, copied_source)

    text = extract_text(inbox_path)
    if text:
        (target_dir / "extracted_text.md").write_text(text, encoding="utf-8")
    metadata = {
        "document_id": doc["document_id"],
        "source_file": str(copied_source),
        "text_extracted": bool(text),
    }
    (target_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return target_dir


def _coverage_checks(manifest: dict[str, Any], seed: dict[str, Any]) -> list[ManifestIssue]:
    issues: list[ManifestIssue] = []
    docs = manifest["documents"]
    categories = {doc["category"] for doc in docs}
    required_categories = {"accounts", "charges", "ownership", "management", "news"}
    missing_categories = required_categories - categories
    for category in sorted(missing_categories):
        issues.append(ManifestIssue("error", f"Missing required category: {category}"))

    accounts_periods = {
        doc.get("reporting_period_end")
        for doc in docs
        if doc["category"] == "accounts" and doc.get("reporting_period_end")
    }
    if len(accounts_periods) < 3:
        issues.append(ManifestIssue("error", "Dataroom requires at least three years of accounts"))

    for fact in seed.get("financial_facts", []):
        if fact.get("value") is None:
            issues.append(
                ManifestIssue(
                    "warning",
                    f"{fact['metric']} for {fact['period_end']} requires source PDF verification",
                    fact["source_document_id"],
                )
            )
    return issues


def _summary(manifest: dict[str, Any], seed: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    return {
        "company": manifest["company"],
        "document_count": len(manifest["documents"]),
        "processed_document_count": sum(1 for doc in result["documents"] if doc["processed"]),
        "charge_count": len(seed.get("charges", [])),
        "event_count": len(seed.get("events", [])),
        "open_issue_count": len(result["issues"]),
        "run_at": result["run_at"],
    }


def _write_report(name: str, payload: dict[str, Any]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
