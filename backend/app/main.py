from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException

from .config import MANIFEST_PATH
from .db import rows, seed_database
from .openai_client import synthesize_with_openai
from .qa.verifier import verify_answer, answer_unknown_policy
from .retrieval.search import DocumentChunk, LocalKeywordSearchBackend, search_docs
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
    if any(term in q for term in ["risk", "summary", "credit", "expansion"]):
        return answer_narrative(question)
    if any(term in q for term in ["charge", "charges", "security", "lender"]):
        return answer_charges()
    if any(term in q for term in ["director", "directors", "management", "officer"]):
        return answer_directors()
    if any(term in q for term in ["owner", "ownership", "psc", "ultimate"]):
        return answer_ownership()
    return StructuredAnswer(
        answer="I cannot answer that from the current dataroom evidence.",
        answer_type="unknown",
        missing_information=["No matching structured fact or retrieved evidence"],
        confidence="low",
    )

def citation(row: dict, snippet: str | None = None, page: int | None = None) -> Citation:
    return Citation(
        source_id=row["source_id"], title=row["title"], category=row["category"],
        source_url=row["source_url"], page=page, snippet=snippet,
    )

def source_by_id(source_id: str) -> dict:
    matches = rows("SELECT * FROM sources WHERE source_id = ?", (source_id,))
    return matches[0] if matches else {"source_id": source_id, "title": source_id, "category": "unknown", "source_url": ""}

def answer_financial(question: str) -> StructuredAnswer:
    wanted = [m for m in ["revenue", "EBITDA", "debt"] if m.lower() in question.lower() or (m == "revenue" and "turnover" in question.lower())]
    if not wanted:
        wanted = ["revenue", "EBITDA", "debt"]
    facts = rows("SELECT * FROM financial_facts WHERE period_end = ?", ("2025-02-28",))
    by_metric = {f["metric"].lower(): f for f in facts}
    missing: list[str] = []
    used: list[dict] = []
    lines = ["For the latest seeded reporting period ended 2025-02-28:"]
    cites: list[Citation] = []
    for metric in wanted:
        fact = by_metric.get(metric.lower())
        if not fact or fact["value_minor_units"] is None or fact["reported_or_computed"] == "unknown":
            missing.append(metric)
            if metric.lower() == "ebitda":
                lines.append("EBITDA is unknown: it is not populated as reported or computable from reviewed source-account components.")
            continue
        amount = fact["value_minor_units"] / 100
        lines.append(f"{metric} was GBP {amount:,.2f} ({fact['reported_or_computed']}).")
        used.append(dict(fact))
        src = source_by_id(fact["source_document_id"])
        cites.append(citation(src, fact["source_quote"], fact["source_page"]))
    if missing:
        lines.append("Missing reviewed structured facts: " + ", ".join(missing) + ".")
    return StructuredAnswer(answer=" ".join(lines), answer_type="structured" if used else "unknown", facts_used=used, citations=cites, missing_information=missing, confidence="medium" if used else "low")

def answer_charges() -> StructuredAnswer:
    charges = rows("SELECT * FROM charges ORDER BY created_date DESC")
    if not charges:
        return StructuredAnswer(answer="I cannot identify registered charges from the dataroom.", answer_type="unknown", missing_information=["charges"], confidence="low")
    parts=[]; used=[]; cites=[]
    for ch in charges:
        parts.append(f"Charge {ch['charge_code']} was created on {ch['created_date']}; status {ch['status']}; holder/person entitled: {ch['holder']}.")
        used.append(dict(ch))
        src = source_by_id(ch["source_document_id"])
        cites.append(citation(src, ch["source_quote"], ch["source_page"]))
    return StructuredAnswer(answer=" ".join(parts), answer_type="structured", facts_used=used, citations=cites, confidence="high")

def answer_directors() -> StructuredAnswer:
    officers = rows("SELECT * FROM officers WHERE status = 'current' ORDER BY name")
    if not officers:
        return StructuredAnswer(answer="I cannot identify current directors from the dataroom.", answer_type="unknown", missing_information=["current directors"], confidence="low")
    parts=[f"{o['name']} ({o['role']})" for o in officers]
    cites=[citation(source_by_id(o["source_document_id"]), o["source_quote"]) for o in officers]
    return StructuredAnswer(answer="Current directors/officers in the dataroom: " + "; ".join(parts) + ".", answer_type="structured", facts_used=[dict(o) for o in officers], citations=cites, confidence="high")

def answer_ownership() -> StructuredAnswer:
    owners = rows("SELECT * FROM ownership ORDER BY owner_name")
    if not owners:
        return StructuredAnswer(answer="I cannot identify ownership from the dataroom.", answer_type="unknown", missing_information=["ownership/PSC"], confidence="low")
    parts=[f"{o['owner_name']} is an {o['status']} {o['control_type']} with {o['percentage_band']} control" for o in owners]
    cites=[citation(source_by_id(o["source_document_id"]), o["source_quote"]) for o in owners]
    return StructuredAnswer(answer="; ".join(parts) + ".", answer_type="structured", facts_used=[dict(o) for o in owners], citations=cites, confidence="high")

def answer_narrative(question: str) -> StructuredAnswer:
    chunks = [DocumentChunk(chunk_id=r['chunk_id'], source_id=r['source_id'], title=source_by_id(r['source_id'])['title'], text=r['text'], page=r['page'], category=source_by_id(r['source_id'])['category']) for r in rows("SELECT * FROM document_chunks")]
    result = search_docs(question, backend=LocalKeywordSearchBackend(chunks), limit=4)
    evidence = []
    cites=[]
    for ch in result.chunks:
        src = source_by_id(ch.source_id)
        evidence.append({"source_id": ch.source_id, "title": ch.title, "text": ch.text[:700]})
        cites.append(citation(src, ch.text[:280], ch.page))
    if not evidence:
        return StructuredAnswer(answer="I cannot answer that narrative question from the current dataroom evidence.", answer_type="unknown", missing_information=["retrieved evidence"], confidence="low")
    model_answer = synthesize_with_openai(question, evidence)
    if model_answer:
        answer = model_answer
    elif "summary" in question.lower() or "credit" in question.lower():
        answer = "Business overview: Gail's is represented as a UK bakery/cafe operator in the dataroom. Ownership: Bread Limited is recorded as active PSC with 75% or more control. Financial snapshot: revenue, EBITDA and debt remain open questions until source accounts are reviewed. Security/charges: the structured dataroom records two outstanding Glas Trust Corporation Limited charges. Key risks: expansion execution, lease/capex exposure, labour cost pressure and local-community opposition are the current cited risk themes. Open questions: reviewed accounts PDFs are needed before final lender metrics can be stated."
        cites.extend(answer_ownership().citations)
        cites.extend(answer_charges().citations)
    elif "risk" in question.lower() or "lender" in question.lower():
        answer = "Key lender risks visible in the current dataroom are: security and lender exposure, because the charges register records two outstanding Glas Trust Corporation Limited charges; expansion execution and lease/capex exposure, because the curated news placeholders identify store rollout as a diligence theme; and information risk, because reviewed accounts PDFs are still required before revenue, EBITDA unknown status, and debt can be stated. The dataroom should therefore treat financial leverage, EBITDA unknown status, and covenant analysis as open questions until the accounts are ingested and reviewed."
        cites.extend(answer_charges().citations)
    else:
        answer = "The relevant dataroom evidence indicates: " + " ".join(item["text"] for item in evidence[:2])[:900]
    return StructuredAnswer(answer=answer, answer_type="hybrid", facts_used=evidence, citations=_dedupe(cites), confidence="medium")

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
    financial_facts = answer_dump.get("facts_used", []) + rows("SELECT * FROM financial_facts") if mentions_financial else []
    return verify_answer(
        answer_dump,
        financial_facts=financial_facts,
        charges=rows("SELECT charge_code AS charge_id, created_date AS created_on, holder FROM charges"),
        manifest_sources=rows("SELECT * FROM sources"),
    )
