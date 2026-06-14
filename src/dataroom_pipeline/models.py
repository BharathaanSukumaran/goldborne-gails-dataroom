from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REQUIRED_DOCUMENT_FIELDS = {
    "document_id",
    "title",
    "category",
    "source",
    "source_url",
    "date",
    "copyright_policy",
}


@dataclass(frozen=True)
class ManifestIssue:
    severity: str
    message: str
    document_id: str | None = None


def validate_manifest(manifest: dict[str, Any]) -> list[ManifestIssue]:
    issues: list[ManifestIssue] = []
    company = manifest.get("company", {})
    if not company.get("company_number"):
        issues.append(ManifestIssue("error", "Manifest company_number is required"))
    if not company.get("legal_name"):
        issues.append(ManifestIssue("error", "Manifest legal_name is required"))

    seen_ids: set[str] = set()
    documents = manifest.get("documents", [])
    if not documents:
        issues.append(ManifestIssue("error", "At least one document is required"))

    for doc in documents:
        document_id = doc.get("document_id")
        missing = sorted(field for field in REQUIRED_DOCUMENT_FIELDS if not doc.get(field))
        if missing:
            issues.append(
                ManifestIssue(
                    "error",
                    f"Missing required fields: {', '.join(missing)}",
                    document_id=document_id,
                )
            )
        if document_id in seen_ids:
            issues.append(ManifestIssue("error", "Duplicate document_id", document_id=document_id))
        if document_id:
            seen_ids.add(document_id)

    return issues
