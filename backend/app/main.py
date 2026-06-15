from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException

from .config import MANIFEST_PATH
from .db import db_path, rows, seed_database
from .facts.answers import build_financial_answer
from .facts.repository import FinancialFactsRepository
from .openai_client import synthesize_with_openai
from .qa.verifier import verify_answer, answer_unknown_policy
from .retrieval.search import DocumentChunk, LocalKeywordSearchBackend, filter_manifest_backed_chunks, search_docs
from .schemas import AskRequest, EvalCaseResult, EvalRunResponse, StructuredAnswer, Citation

app = FastAPI(title="Goldborne Gail's Dataroom API", version="0.1.0")

@app.on_event("startup")
def startup() -> None:
    seed_database()

@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "gails-dataroom-api"}

@app.get("/sources")
def sources() -> dict:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {"company": data.get("company"), "sources": data.get("sources", [])}

@app.get("/sources/{source_id}")
def source(source_id: str) -> dict:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for item in data.get("sources", []):
        if item["source_id"] == source_id:
            return item
    raise HTTPException(status_code=404, detail="source_id not found")

@app.post("/ask", response_model=StructuredAnswer)
def ask(request: AskRequest) -> StructuredAnswer:
    seed_database()
    answer = answer_question(request.question)
    result = verify_structured_answer(answer)
    if not result.passed:
        return StructuredAnswer(**result.answer)
    return StructuredAnswer(**result.answer)

@app.post("/evals/run", response_model=EvalRunResponse)
def run_evals() -> EvalRunResponse:
    cases = [
        "What was revenue and EBITDA in the last reported year?",
        "What charges are registered against the company and who holds them?",
        "Who are the current directors?",
        "What are the key risks for a lender?",
        "What are the private bank covenants?",
    ]
    results: list[EvalCaseResult] = []
    for question in cases:
        ans = answer_question(question)
        dumped = ans.model_dump()
        result = verify_structured_answer(ans)
        has_citation_or_unknown = bool(ans.citations) or ans.answer_type == "unknown"
        passed = result.passed and has_citation_or_unknown
        results.append(EvalCaseResult(question=question, passed=passed, answer_type=ans.answer_type, notes=list(result.errors)))
    return EvalRunResponse(passed=all(r.passed for r in results), results=results)

def answer_question(question: str) -> StructuredAnswer:
    unknown = answer_unknown_policy(question)
    if unknown.should_answer_unknown:
        return StructuredAnswer(
            answer="I cannot answer that from the current dataroom evidence.",
            answer_type="unknown",
            missing_information=list(unknown.missing_information),
            confidence="low",
        )
    q = question.lower()
    if any(term in q for term in ["revenue", "ebitda", "debt", "borrowings"]):
        return answer_financial(question)
    if any(term in q for term in ["charge", "charges", "security", "lender"]):
        return answer_charges()
    if any(term in q for term in ["director", "directors", "management", "officer"]):
        return answer_directors()
    if any(term in q for term in ["owner", "ownership", "psc", "ultimate"]):
        return answer_ownership()
    if any(term in q for term in ["risk", "summary", "credit", "expansion"]):
        return answer_narrative(question)
    return StructuredAnswer(
        answer="This is not available in the current dataroom.",
        answer_type="unknown",
        missing_information=["No matching structured fact or retrieved evidence"],
        confidence="low",
    )

def citation(row: dict, snippet: str | None = None, page: int | None = None) -> Citation:
    return Citation(
        source_id=row["source_id"], title=row["title"], category=row["category"],
        source_url=row["source_url"], page=page, snippet=snippet,
    )

def source_by_id(source_id: str) -> dict | None:
    matches = rows("SELECT * FROM sources WHERE source_id = ?", (source_id,))
    return matches[0] if matches else None

def unknown_answer(missing: list[str], answer: str = "I cannot answer that from the current dataroom evidence.") -> StructuredAnswer:
    return StructuredAnswer(answer=answer, answer_type="unknown", missing_information=missing, confidence="low")

def answer_financial(question: str) -> StructuredAnswer:
    payload = build_financial_answer(question, FinancialFactsRepository(db_path()))
    citations: list[Citation] = []
    missing_sources: list[str] = []
    for raw_citation in payload.get("citations", []):
        source_id = raw_citation.get("source_document_id") or raw_citation.get("source_id")
        if not source_id:
            missing_sources.append("citation source_id")
            continue
        src = source_by_id(source_id)
        if src is None:
            missing_sources.append(f"manifest source {source_id}")
            continue
        citations.append(citation(src, raw_citation.get("source_quote"), raw_citation.get("source_page")))

    if missing_sources or (payload.get("answer_type") != "unknown" and not citations):
        return unknown_answer(
            [*payload.get("missing_information", []), *missing_sources],
            "I cannot answer this financial question because the supporting source is not in the manifest.",
        )

    return StructuredAnswer(
        answer=payload["answer"],
        answer_type=payload["answer_type"],
        facts_used=payload.get("facts_used", []),
        citations=citations,
        missing_information=payload.get("missing_information", []),
        confidence=payload.get("confidence", "low"),
    )

def answer_charges() -> StructuredAnswer:
    charges = rows("SELECT * FROM charges ORDER BY created_date DESC")
    if not charges:
        return StructuredAnswer(answer="I cannot identify registered charges from the dataroom.", answer_type="unknown", missing_information=["charges"], confidence="low")
    parts=[]; used=[]; cites=[]
    for ch in charges:
        parts.append(f"Charge {ch['charge_code']} was created on {ch['created_date']}; status {ch['status']}; holder/person entitled: {ch['holder']}.")
        used.append(dict(ch))
        src = source_by_id(ch["source_document_id"])
        if src is None:
            return unknown_answer([f"manifest source {ch['source_document_id']}"], "I cannot answer charges because the supporting source is not in the manifest.")
        cites.append(citation(src, ch["source_quote"], ch["source_page"]))
    return StructuredAnswer(answer=" ".join(parts), answer_type="charges_security", facts_used=used, citations=cites, confidence="high")

def answer_directors() -> StructuredAnswer:
    officers = rows("SELECT * FROM officers WHERE status = 'current' ORDER BY name")
    if not officers:
        return StructuredAnswer(answer="I cannot identify current directors from the dataroom.", answer_type="unknown", missing_information=["current directors"], confidence="low")
    parts=[f"{o['name']} ({o['role']})" for o in officers]
    cites=[]
    for o in officers:
        src = source_by_id(o["source_document_id"])
        if src is None:
            return unknown_answer([f"manifest source {o['source_document_id']}"], "I cannot answer current directors because the supporting source is not in the manifest.")
        cites.append(citation(src, o["source_quote"]))
    return StructuredAnswer(answer="Current directors/officers in the dataroom: " + "; ".join(parts) + ".", answer_type="ownership_management", facts_used=[dict(o) for o in officers], citations=cites, confidence="high")

def answer_ownership() -> StructuredAnswer:
    owners = rows("SELECT * FROM ownership ORDER BY owner_name")
    if not owners:
        return StructuredAnswer(answer="I cannot identify ownership from the dataroom.", answer_type="unknown", missing_information=["ownership/PSC"], confidence="low")
    parts=[f"{o['owner_name']} is an {o['status']} {o['control_type']} with {o['percentage_band']} control" for o in owners]
    cites=[]
    for o in owners:
        src = source_by_id(o["source_document_id"])
        if src is None:
            return unknown_answer([f"manifest source {o['source_document_id']}"], "I cannot answer ownership because the supporting source is not in the manifest.")
        cites.append(citation(src, o["source_quote"]))
    return StructuredAnswer(answer="; ".join(parts) + ".", answer_type="ownership_management", facts_used=[dict(o) for o in owners], citations=cites, confidence="high")

def answer_narrative(question: str) -> StructuredAnswer:
    manifest_sources = rows("SELECT * FROM sources")
    chunk_rows = rows("""
        SELECT dc.chunk_id, dc.source_id, dc.page, dc.text, s.title, s.category
        FROM document_chunks dc
        JOIN sources s ON s.source_id = dc.source_id
    """)
    chunks = [
        DocumentChunk(
            chunk_id=r["chunk_id"],
            source_id=r["source_id"],
            title=r["title"],
            text=r["text"],
            page=r["page"],
            category=r["category"],
        )
        for r in chunk_rows
    ]
    result = search_docs(question, backend=LocalKeywordSearchBackend(chunks), limit=4)
    backed_chunks = filter_manifest_backed_chunks(result.chunks, manifest_sources)
    evidence = []
    cites=[]
    for ch in backed_chunks:
        src = source_by_id(ch.source_id)
        if src is None:
            continue
        snippet = ch.text[:700].strip()
        if not snippet:
            continue
        evidence.append({
            "source_id": ch.source_id,
            "title": ch.title,
            "category": ch.category,
            "page": ch.page,
            "snippet": snippet,
        })
        cites.append(citation(src, snippet[:280], ch.page))
    if not evidence:
        return StructuredAnswer(answer="I cannot answer that narrative question from the current dataroom evidence.", answer_type="unknown", missing_information=["retrieved manifest-backed evidence"], confidence="low")
    model_answer = synthesize_with_openai(question, evidence)
    answer = model_answer.strip() if model_answer and model_answer.strip() else _snippet_answer(evidence)
    return StructuredAnswer(answer=answer, answer_type="credit_summary", facts_used=evidence, citations=_dedupe(cites), confidence="medium")

def _snippet_answer(evidence: list[dict]) -> str:
    parts = []
    for item in evidence[:3]:
        snippet = str(item.get("snippet") or "").strip()
        if snippet:
            parts.append(f"{item['title']}: {snippet}")
    return "Retrieved dataroom snippets state: " + " ".join(parts)[:1200]

def _dedupe(citations: list[Citation]) -> list[Citation]:
    seen=set(); out=[]
    for c in citations:
        key=(c.source_id,c.page,c.snippet)
        if key not in seen:
            seen.add(key); out.append(c)
    return out

def verify_structured_answer(answer: StructuredAnswer):
    answer_dump = answer.model_dump()
    mentions_financial = any(
        str(fact.get("metric", "")).lower() in {"revenue", "ebitda", "debt"}
        for fact in answer_dump.get("facts_used", [])
        if isinstance(fact, dict)
    ) or "ebitda" in answer_dump.get("answer", "").lower()
    financial_facts = rows("SELECT * FROM financial_facts") if mentions_financial else []
    return verify_answer(
        answer_dump,
        financial_facts=financial_facts,
        charges=rows("SELECT charge_code AS charge_id, created_date AS created_on, holder FROM charges"),
        manifest_sources=rows("SELECT * FROM sources"),
    )
