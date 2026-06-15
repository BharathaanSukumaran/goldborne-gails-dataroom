#!/usr/bin/env python3
"""Process manifest sources into page-level text records.

The processor is intentionally fixture-friendly: it uses local files only and
falls back to clear error records when PDF text extraction is unavailable or
produces blank output. Existing curated Markdown files are preserved.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "dataroom" / "manifest.json"
DEFAULT_REPORT = ROOT / "dataroom" / "processed" / "source_coverage_report.json"
DEFAULT_PROCESSED_DIR = ROOT / "dataroom" / "processed"
ACCOUNTS_TEXT_DIR = DEFAULT_PROCESSED_DIR / "accounts_text"

PROCESSED_PATH_BY_SOURCE_ID = {
    "ch-profile-06055393": "dataroom/processed/ch_profile_06055393.md",
    "ch-filing-history-06055393": "dataroom/processed/ch_filing_history_06055393.md",
    "ch-charges-register-06055393": "dataroom/processed/ch_charges_register.md",
    "ch-charge-0006": "dataroom/processed/ch_charge_0006.md",
    "ch-charge-0005": "dataroom/processed/ch_charge_0005.md",
    "ch-officers-06055393": "dataroom/processed/ch_officers_06055393.md",
    "ch-psc-06055393": "dataroom/processed/ch_psc_06055393.md",
    "news-expansion-2025-placeholder": "dataroom/processed/guardian_expansion_2025.md",
    "news-community-context-2024-placeholder": "dataroom/processed/guardian_community_2024.md",
}


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def source_status_for(processing_status: str) -> str:
    if processing_status == "verified":
        return "verified"
    if processing_status == "processed":
        return "processed"
    return "pending"


def processed_path_for(source: dict[str, Any]) -> str | None:
    value = source.get("processed_path") or PROCESSED_PATH_BY_SOURCE_ID.get(source["source_id"])
    return str(value) if value else None


def page_record(source: dict[str, Any], page: int, text: str) -> dict[str, Any]:
    return {
        "source_id": source["source_id"],
        "page": page,
        "title": source["title"],
        "category": source["category"],
        "issuer": source["issuer"],
        "retrieved_at": source["retrieved_at"],
        "text": text.strip(),
    }


def error_record(source: dict[str, Any], message: str) -> dict[str, Any]:
    return {
        "source_id": source["source_id"],
        "page": None,
        "title": source["title"],
        "category": source["category"],
        "issuer": source["issuer"],
        "retrieved_at": source["retrieved_at"],
        "error": message,
    }


def meaningful_text(text: str) -> bool:
    return sum(1 for char in text if char.isalnum()) > 200


def split_pages(text: str) -> list[str]:
    pages = text.split("\f") if "\f" in text else [text]
    return [page.strip() for page in pages]


def extract_pdf_text(pdf_path: Path) -> tuple[str, str | None]:
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        return "", "pdftotext is not installed"
    except subprocess.TimeoutExpired:
        return "", "pdftotext timed out"
    if result.returncode != 0:
        stderr = result.stderr.strip() or f"pdftotext exited with {result.returncode}"
        return "", stderr
    return result.stdout, None


def process_source(source: dict[str, Any], root: Path, processed_dir: Path) -> dict[str, Any]:
    raw_path = root / source["local_path"]
    if not raw_path.exists():
        return {"status": source["processing_status"], "processed_path": source.get("processed_path"), "error": "raw source is missing"}

    suffix = raw_path.suffix.lower()
    if suffix == ".pdf":
        text, error = extract_pdf_text(raw_path)
        if error is None and meaningful_text(text):
            text_path = ACCOUNTS_TEXT_DIR / f"{source['source_id']}.txt" if source["category"] == "accounts" else processed_dir / f"{source['source_id']}.txt"
            text_path.parent.mkdir(parents=True, exist_ok=True)
            text_path.write_text(text, encoding="utf-8")
            records = [
                page_record(source, index, page)
                for index, page in enumerate(split_pages(text), start=1)
                if page.strip()
            ]
            records_path = processed_dir / f"{source['source_id']}.pages.json"
            records_path.write_text(json.dumps({"pages": records}, indent=2) + "\n", encoding="utf-8")
            return {"status": "processed", "processed_path": str(text_path.relative_to(root)), "page_count": len(records), "error": None}

        message = error or "PDF text extraction produced no meaningful text; OCR/manual review required"
        error_path = processed_dir / f"{source['source_id']}.processing_error.json"
        error_path.write_text(json.dumps(error_record(source, message), indent=2) + "\n", encoding="utf-8")
        return {"status": "processing_failed", "processed_path": str(error_path.relative_to(root)), "page_count": 0, "error": message}

    if suffix in {".txt", ".md", ".html", ".htm", ".json"}:
        text = raw_path.read_text(encoding="utf-8", errors="ignore")
        if not meaningful_text(text):
            error_path = processed_dir / f"{source['source_id']}.processing_error.json"
            message = "Text-like source contains no meaningful text"
            error_path.write_text(json.dumps(error_record(source, message), indent=2) + "\n", encoding="utf-8")
            return {"status": "processing_failed", "processed_path": str(error_path.relative_to(root)), "page_count": 0, "error": message}
        output_path = processed_dir / f"{source['source_id']}.txt"
        output_path.write_text(text, encoding="utf-8")
        records_path = processed_dir / f"{source['source_id']}.pages.json"
        records_path.write_text(json.dumps({"pages": [page_record(source, 1, text)]}, indent=2) + "\n", encoding="utf-8")
        return {"status": "processed", "processed_path": str(output_path.relative_to(root)), "page_count": 1, "error": None}

    message = f"Unsupported source file type: {suffix or 'unknown'}"
    error_path = processed_dir / f"{source['source_id']}.processing_error.json"
    error_path.write_text(json.dumps(error_record(source, message), indent=2) + "\n", encoding="utf-8")
    return {"status": "processing_failed", "processed_path": str(error_path.relative_to(root)), "page_count": 0, "error": message}


def process_documents(manifest: dict[str, Any], root: Path = ROOT, processed_dir: Path = DEFAULT_PROCESSED_DIR) -> dict[str, Any]:
    processed_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}
    for source in manifest["sources"]:
        if source.get("processed_path") and (root / source["processed_path"]).exists() and source.get("processing_status") in {"processed", "verified"}:
            results[source["source_id"]] = {
                "status": source["processing_status"],
                "processed_path": source["processed_path"],
                "page_count": source.get("page_count") or source.get("pages") or 1,
                "error": None,
            }
            continue
        if source.get("processing_status") not in {"downloaded", "failed", "processing_failed"}:
            results[source["source_id"]] = {"status": source["processing_status"], "processed_path": source.get("processed_path"), "error": None}
            continue
        result = process_source(source, root, processed_dir)
        source["processing_status"] = result["status"]
        source["source_status"] = source_status_for(result["status"])
        if result.get("processed_path"):
            source["processed_path"] = result["processed_path"]
        if "page_count" in result:
            source["page_count"] = result["page_count"]
        results[source["source_id"]] = result
    return results


def source_state(source: dict[str, Any], root: Path) -> dict[str, Any]:
    local_path = root / source["local_path"]
    processed_path = processed_path_for(source)
    raw_exists = local_path.exists()
    processed_exists = bool(processed_path and (root / processed_path).exists())
    status = source["processing_status"]
    source_status = source_status_for(status)
    issue = None

    if status == "processing_failed":
        issue = "source processing failed; inspect processed error record"
    elif status == "failed":
        issue = "source download failed"
    elif status == "processed" and not processed_exists:
        issue = "manifest status claims processed output but processed file is missing"
    elif status == "verified" and not processed_exists:
        issue = "manifest status claims verified output but processed file is missing"
    elif status == "downloaded" and not raw_exists:
        issue = "manifest status claims downloaded source but raw file is missing"
    elif status in {"pending_download", "pending_manual_curation"} and not raw_exists and not processed_exists:
        issue = "expected source is not present yet"

    return {
        "source_id": source["source_id"],
        "category": source["category"],
        "title": source["title"],
        "processing_status": status,
        "source_status": source_status,
        "local_path": source["local_path"],
        "local_exists": raw_exists,
        "processed_path": processed_path,
        "processed_exists": processed_exists,
        "page_count": source.get("page_count") or source.get("pages") or 0,
        "issue": issue,
    }


def build_report(manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    states = [source_state(source, root) for source in manifest["sources"]]
    category_counts = Counter(source["category"] for source in manifest["sources"])
    status_counts = Counter(source["processing_status"] for source in manifest["sources"])
    source_status_counts = Counter(state["source_status"] for state in states)
    required = set(manifest["coverage"]["required_categories"])
    covered = set(category_counts)
    missing = sorted(required - covered)

    latest_accounts = [
        {
            "source_id": source["source_id"],
            "period_end": source.get("period_end"),
            "filed_at": source.get("filed_at"),
            "pages": source.get("pages"),
            "page_count": source.get("page_count") or 0,
            "processing_status": source["processing_status"],
            "source_status": source_status_for(source["processing_status"]),
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
        "source_status_counts": dict(sorted(source_status_counts.items())),
        "required_categories_missing": missing,
        "latest_three_accounts": sorted(latest_accounts, key=lambda item: item["period_end"], reverse=True),
        "companies_house_sources": [state["source_id"] for state in states if state["category"] != "news"],
        "curated_news_placeholders": [state["source_id"] for state in states if state["category"] == "news"],
        "issues": [state for state in states if state["issue"]],
        "sources": states,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--update-manifest", action="store_true", help="Write derived source_status values back to the manifest.")
    parser.add_argument("--process", action="store_true", help="Convert downloaded raw files into page text or processing error records.")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    if args.process:
        process_documents(manifest, ROOT, DEFAULT_PROCESSED_DIR)
        args.update_manifest = True
    report = build_report(manifest, ROOT)
    if args.update_manifest:
        state_by_id = {state["source_id"]: state for state in report["sources"]}
        for source in manifest["sources"]:
            state = state_by_id[source["source_id"]]
            source["source_status"] = state["source_status"]
            if state["processed_exists"] and state["processed_path"]:
                source["processed_path"] = state["processed_path"]
                if source["processing_status"] not in {"processed", "verified", "processing_failed"}:
                    source["processing_status"] = "processed"
                source["source_status"] = source_status_for(source["processing_status"])
            elif state["local_exists"] and source["processing_status"] in {"pending_download", "pending_manual_curation"}:
                source["processing_status"] = "downloaded"
                source["source_status"] = source_status_for(source["processing_status"])
            else:
                source["source_status"] = source_status_for(source["processing_status"])
        args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        report = build_report(manifest, ROOT)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {args.output}")
    print(f"Sources: {report['source_count']}")
    print(f"Missing required categories: {', '.join(report['required_categories_missing']) or 'none'}")
    print(f"Issues: {len(report['issues'])}")


if __name__ == "__main__":
    main()
