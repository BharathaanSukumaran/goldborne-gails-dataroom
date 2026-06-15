from pathlib import Path

from scripts.ingest_companies_house import build_manifest
from scripts.process_documents import build_report, load_manifest
from scripts.test_submission import validate_manifest


ROOT = Path(__file__).resolve().parents[2]


def test_ingestion_manifest_preserves_processed_sources():
    manifest = build_manifest("2026-06-15T00:00:00Z")
    sources = {source["source_id"]: source for source in manifest["sources"]}

    assert sources["ch-profile-06055393"]["processing_status"] == "processed"
    assert sources["ch-profile-06055393"]["source_status"] == "processed"
    assert sources["ch-profile-06055393"]["processed_path"] == "dataroom/processed/ch_profile_06055393.md"
    assert sources["ch-parent-accounts-2025"]["processing_status"] == "downloaded"
    assert sources["ch-parent-accounts-2025"]["source_status"] == "pending"


def test_source_coverage_report_has_no_missing_required_categories():
    manifest = load_manifest(ROOT / "dataroom" / "manifest.json")
    report = build_report(manifest, ROOT)

    assert report["required_categories_missing"] == []
    assert report["source_count"] >= 12
    assert len(report["latest_three_accounts"]) == 3
    assert report["source_status_counts"]["processed"] >= 9


def test_submission_manifest_validation_passes_current_manifest():
    assert validate_manifest() == []
