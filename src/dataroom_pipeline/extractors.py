from __future__ import annotations

from pathlib import Path


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".html", ".htm"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        return _extract_pdf_text(path)
    return ""


def _extract_pdf_text(path: Path) -> str:
    try:
        import fitz  # type: ignore
    except Exception:
        return ""

    chunks: list[str] = []
    with fitz.open(path) as doc:
        for page_number, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if text:
                chunks.append(f"\n\n--- Page {page_number} ---\n{text}")
    return "\n".join(chunks).strip()
