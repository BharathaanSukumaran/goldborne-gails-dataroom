import pytest

from backend.app.retrieval import (
    DocumentPage,
    LocalKeywordSearchBackend,
    OpenAIFileSearchBackend,
    chunk_document_pages,
    search_docs,
)


def test_chunking_preserves_source_id_page_and_title():
    pages = [
        DocumentPage(
            source_id="accounts-2024",
            title="GAIL's Limited accounts 2024",
            page=12,
            category="financial_filings",
            text=("Business overview and principal activities. " * 80),
            metadata={"issuer": "Companies House"},
        )
    ]

    chunks = chunk_document_pages(pages, max_chars=300, overlap_chars=40)

    assert len(chunks) > 1
    assert {chunk.source_id for chunk in chunks} == {"accounts-2024"}
    assert {chunk.page for chunk in chunks} == {12}
    assert {chunk.title for chunk in chunks} == {"GAIL's Limited accounts 2024"}
    assert chunks[0].metadata["issuer"] == "Companies House"


def test_local_search_returns_snippets_with_citation_metadata():
    chunks = chunk_document_pages(
        [
            DocumentPage(
                source_id="news-expansion",
                title="Expansion article",
                page=1,
                category="news",
                text="GAIL's opened new bakeries in commuter towns and continued expansion.",
            ),
            DocumentPage(
                source_id="accounts-2024",
                title="Accounts",
                page=3,
                category="financial_filings",
                text="The strategic report discusses inflationary pressure on input costs.",
            ),
        ]
    )

    response = search_docs("expansion in commuter towns", chunks=chunks, limit=2)

    assert not response.requires_structured_facts
    assert response.chunks[0].source_id == "news-expansion"
    assert response.chunks[0].page == 1
    assert "commuter towns" in response.chunks[0].text
    assert response.chunks[0].score > 0


def test_exact_financial_query_is_flagged_for_structured_facts_not_retrieval():
    chunks = chunk_document_pages(
        [
            DocumentPage(
                source_id="accounts-2024",
                title="Accounts",
                page=20,
                text="The company reported revenue in the period.",
            )
        ]
    )

    response = search_docs("What was revenue and EBITDA in the last reported year?", chunks=chunks)

    assert response.requires_structured_facts
    assert response.warning is not None
    assert "facts database" in response.warning
    assert response.chunks


def test_openai_file_search_adapter_requires_source_metadata():
    backend = OpenAIFileSearchBackend(
        lambda query, limit: [
            {
                "text": "Expansion and trading narrative.",
                "metadata": {
                    "source_id": "news-1",
                    "title": "News source",
                    "page": "2",
                    "category": "news",
                },
                "score": 0.72,
            }
        ]
    )

    result = backend.search("expansion", limit=1)[0]

    assert result.source_id == "news-1"
    assert result.page == 2
    assert result.title == "News source"
    assert result.category == "news"
    assert result.score == 0.72


def test_openai_file_search_adapter_rejects_results_without_source_id():
    backend = OpenAIFileSearchBackend(lambda query, limit: [{"text": "No source metadata"}])

    with pytest.raises(ValueError, match="source_id"):
        backend.search("anything")
