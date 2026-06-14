"""Chunking and retrieval abstractions for dataroom documents.

Retrieval is intentionally scoped to narrative evidence. Exact financial,
charge, ownership, and officer answers should be served from structured fact
tables by the API layer; this module only flags those questions so callers can
route them correctly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import log
import re
from typing import Any, Iterable, Mapping, Protocol, Sequence


TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9&'._-]*", re.IGNORECASE)
EXACT_FACT_TERMS = {
    "revenue",
    "turnover",
    "ebitda",
    "debt",
    "borrowings",
    "cash",
    "profit",
    "loss",
    "assets",
    "liabilities",
    "charge",
    "charges",
    "lender",
    "lenders",
    "director",
    "directors",
    "ownership",
    "owner",
    "psc",
    "shareholder",
}


@dataclass(frozen=True)
class DocumentPage:
    """One page or page-like unit extracted from a source document."""

    source_id: str
    title: str
    text: str
    page: int | None = None
    category: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DocumentChunk:
    """A searchable text chunk with citation metadata preserved."""

    chunk_id: str
    source_id: str
    title: str
    text: str
    page: int | None = None
    category: str | None = None
    score: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchResponse:
    """Search results plus routing guidance for the answer layer."""

    query: str
    chunks: list[DocumentChunk]
    requires_structured_facts: bool = False
    warning: str | None = None


class SearchBackend(Protocol):
    """Minimal interface shared by local and hosted retrieval backends."""

    def search(self, query: str, *, limit: int = 5) -> list[DocumentChunk]:
        ...


def filter_manifest_backed_chunks(
    chunks: Iterable[DocumentChunk],
    manifest_sources: Iterable[Mapping[str, Any] | Any],
) -> list[DocumentChunk]:
    """Keep only chunks whose source_id resolves to a source manifest entry."""

    manifest_ids = {
        str(_field(source, "source_id") or _field(source, "id"))
        for source in manifest_sources
        if _field(source, "source_id") or _field(source, "id")
    }
    return [chunk for chunk in chunks if chunk.source_id in manifest_ids]


def chunk_document_pages(
    pages: Iterable[DocumentPage],
    *,
    max_chars: int = 1_200,
    overlap_chars: int = 160,
) -> list[DocumentChunk]:
    """Split document pages into chunks without dropping citation metadata."""

    if max_chars < 200:
        raise ValueError("max_chars must be at least 200")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be non-negative and smaller than max_chars")

    chunks: list[DocumentChunk] = []
    for page in pages:
        text = _normalize_text(page.text)
        if not text:
            continue

        start = 0
        part = 1
        while start < len(text):
            end = _chunk_end(text, start, max_chars)
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(
                    DocumentChunk(
                        chunk_id=_chunk_id(page.source_id, page.page, part),
                        source_id=page.source_id,
                        title=page.title,
                        text=chunk_text,
                        page=page.page,
                        category=page.category,
                        metadata=dict(page.metadata),
                    )
                )
                part += 1
            if end >= len(text):
                break
            start = max(0, end - overlap_chars)
    return chunks


class LocalKeywordSearchBackend:
    """Small deterministic fallback used for local development and tests."""

    def __init__(self, chunks: Sequence[DocumentChunk]):
        self._chunks = list(chunks)
        self._doc_tokens = [_tokens(chunk.text) for chunk in self._chunks]
        self._document_frequency = self._compute_document_frequency(self._doc_tokens)

    def search(self, query: str, *, limit: int = 5) -> list[DocumentChunk]:
        query_terms = _tokens(query)
        if not query_terms or limit <= 0:
            return []

        scored: list[tuple[float, DocumentChunk]] = []
        total_docs = max(1, len(self._chunks))
        for chunk, terms in zip(self._chunks, self._doc_tokens, strict=True):
            if not terms:
                continue
            score = 0.0
            for term in query_terms:
                term_count = terms.count(term)
                if term_count == 0:
                    continue
                inverse_doc_frequency = log((1 + total_docs) / (1 + self._document_frequency[term])) + 1
                score += term_count * inverse_doc_frequency
            if score:
                scored.append((score, chunk))

        scored.sort(key=lambda item: (-item[0], item[1].source_id, item[1].page or 0, item[1].chunk_id))
        return [
            DocumentChunk(
                chunk_id=chunk.chunk_id,
                source_id=chunk.source_id,
                title=chunk.title,
                text=chunk.text,
                page=chunk.page,
                category=chunk.category,
                score=round(score, 6),
                metadata=dict(chunk.metadata),
            )
            for score, chunk in scored[:limit]
        ]

    @staticmethod
    def _compute_document_frequency(doc_tokens: Sequence[list[str]]) -> dict[str, int]:
        frequencies: dict[str, int] = {}
        for terms in doc_tokens:
            for term in set(terms):
                frequencies[term] = frequencies.get(term, 0) + 1
        return frequencies


class OpenAIFileSearchBackend:
    """Adapter for OpenAI file_search results.

    The API integration can inject a callable that performs the OpenAI request.
    Keeping the network call outside this class makes the retrieval contract
    testable and keeps source/page metadata normalization in one place.
    """

    def __init__(self, search_callable: Any):
        self._search_callable = search_callable

    def search(self, query: str, *, limit: int = 5) -> list[DocumentChunk]:
        raw_results = self._search_callable(query=query, limit=limit)
        return [self._from_openai_result(index, item) for index, item in enumerate(raw_results, start=1)]

    @staticmethod
    def _from_openai_result(index: int, item: Mapping[str, Any]) -> DocumentChunk:
        metadata = dict(item.get("metadata") or item.get("attributes") or {})
        source_id = str(metadata.get("source_id") or item.get("source_id") or "")
        if not source_id:
            raise ValueError("OpenAI file_search result is missing source_id metadata")

        page_value = metadata.get("page") or item.get("page")
        page = int(page_value) if page_value not in (None, "") else None
        title = str(metadata.get("title") or item.get("title") or source_id)
        text = str(item.get("text") or item.get("snippet") or "")
        chunk_id = str(item.get("chunk_id") or metadata.get("chunk_id") or f"openai:{source_id}:{page or 'na'}:{index}")

        return DocumentChunk(
            chunk_id=chunk_id,
            source_id=source_id,
            title=title,
            text=text,
            page=page,
            category=metadata.get("category") or item.get("category"),
            score=float(item.get("score") or 0.0),
            metadata=metadata,
        )


def search_docs(
    query: str,
    *,
    backend: SearchBackend | None = None,
    chunks: Sequence[DocumentChunk] | None = None,
    limit: int = 5,
) -> SearchResponse:
    """Search narrative document chunks and flag exact-fact questions."""

    if backend is None:
        backend = LocalKeywordSearchBackend(chunks or [])

    requires_structured_facts = looks_like_exact_fact_query(query)
    warning = None
    if requires_structured_facts:
        warning = (
            "This query appears to require structured facts. Use the facts database "
            "for exact financials, charges, directors, or ownership; retrieval snippets "
            "are narrative evidence only."
        )

    return SearchResponse(
        query=query,
        chunks=backend.search(query, limit=limit),
        requires_structured_facts=requires_structured_facts,
        warning=warning,
    )


def looks_like_exact_fact_query(query: str) -> bool:
    terms = set(_tokens(query))
    if not terms.intersection(EXACT_FACT_TERMS):
        return False
    exact_modifiers = {
        "what",
        "who",
        "which",
        "how",
        "much",
        "many",
        "last",
        "latest",
        "current",
        "registered",
        "against",
        "held",
        "holds",
        "amount",
        "value",
        "year",
        "period",
    }
    return bool(terms.intersection(exact_modifiers)) or any(char.isdigit() for char in query)


def _chunk_id(source_id: str, page: int | None, part: int) -> str:
    page_part = f"p{page}" if page is not None else "pna"
    return f"{source_id}:{page_part}:c{part}"


def _chunk_end(text: str, start: int, max_chars: int) -> int:
    hard_end = min(len(text), start + max_chars)
    if hard_end == len(text):
        return hard_end
    window = text[start:hard_end]
    paragraph_break = window.rfind("\n\n")
    if paragraph_break >= max_chars // 2:
        return start + paragraph_break
    sentence_break = max(window.rfind(". "), window.rfind("? "), window.rfind("! "))
    if sentence_break >= max_chars // 2:
        return start + sentence_break + 1
    whitespace = window.rfind(" ")
    if whitespace >= max_chars // 2:
        return start + whitespace
    return hard_end


def _normalize_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text.replace("\r\n", "\n")).strip()


def _tokens(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(text)]


def _field(item: Mapping[str, Any] | Any, name: str) -> Any:
    if isinstance(item, Mapping):
        return item.get(name)
    return getattr(item, name, None)
