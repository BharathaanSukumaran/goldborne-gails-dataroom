from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException

from .config import MANIFEST_PATH, PROJECT_ROOT
from .db import db_path, rows, seed_database
from .facts.answers import build_financial_answer
from .facts.repository import FinancialFactsRepository
from .openai_client import synthesize_with_openai
from .qa.verifier import verify_answer, answer_unknown_policy
from .retrieval.search import DocumentChunk, LocalKeywordSearchBackend, filter_manifest_backed_chunks, search_docs
from .schemas import AskRequest, EvalCaseResult, EvalRunResponse, StructuredAnswer, Citation

app = FastAPI(title="Goldborne Gail's Dataroom API", version="0.1.0")

CHARGE_TOPIC_TERMS = ("charge", "charges", "security", "lender", "persons entitled")
CHARGE_FIELD_TERMS = (
    "holder",
    "holds",
    "held by",
    "person entitled",
    "persons entitled",
    "lender",
    "status",
    "created",
    "registered",
    "outstanding",
    "satisfied",
    "description",
    "short particulars",
    "particulars",
    "assets",
    "secured",
    "property charged",
    "fixed",
    "floating",
    "obligations",
    "instrument",
    "debenture",
)

CHARGE_FACTS_PATH = PROJECT_ROOT / "backend" / "data" / "charge_facts.json"
CHARGE_FIELD_LABELS = {
    "list_charges": "registered charges",
    "charge_holder": "charge holder",
    "charge_status": "charge status",
    "charge_created_date": "charge created date",
    "charge_delivered_date": "charge delivered date",
    "charge_satisfied_date": "charge satisfied date",
    "charge_description": "charge description",
    "charge_short_particulars": "short particulars",
    "secured_assets": "secured assets",
    "security_type": "security type",
    "obligations_secured": "obligations secured",
    "charge_instrument_summary": "charge instrument summary",
    "charge_document_lookup": "charge instrument text",
    "unknown_charge_field": "charge field",
}
CHARGE_FIELD_TO_FACT_KEY = {
    "charge_holder": "holder",
    "charge_status": "status",
    "charge_created_date": "createdDate",
    "charge_delivered_date": "deliveredDate",
    "charge_satisfied_date": "satisfiedDate",
    "charge_description": "description",
    "charge_short_particulars": "shortParticulars",
    "secured_assets": "securedAssets",
    "security_type": "securityType",
    "obligations_secured": "obligationsSecured",
    "charge_instrument_summary": "instrumentSummary",
    "charge_document_lookup": "instrumentSummary",
}
LEGAL_FIELD_INTENTS = {
    "charge_description",
    "charge_short_particulars",
    "secured_assets",
    "security_type",
    "obligations_secured",
    "charge_instrument_summary",
    "charge_document_lookup",
}

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
    if is_charge_question(q):
        return answer_charges(question)
    if any(term in q for term in ["revenue", "ebitda", "debt", "borrowings"]):
        return answer_financial(question)
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

def is_charge_question(q: str) -> bool:
    if any(term in q for term in CHARGE_TOPIC_TERMS):
        return True
    has_charge_field_intent = any(term in q for term in CHARGE_FIELD_TERMS)
    has_charge_reference = bool(_charge_reference_tokens(q))
    if has_charge_reference and re.search(r"\bwhat\s+(?:is|was|are|were)?\s*(?:the\s+)?(?:specific\s+)?charge\b", q):
        return True
    return has_charge_field_intent and has_charge_reference

def _charge_reference_tokens(q: str) -> set[str]:
    tokens: set[str] = set()
    compact = "".join(ch for ch in q if ch.isalnum())
    for suffix in ("0005", "0006"):
        if suffix in q or f"06055393{suffix}" in compact:
            tokens.add(suffix)
    for year in ("2021", "2022"):
        if year in q:
            tokens.add(year)
    if "latest" in q or "newest" in q or "most recent" in q:
        tokens.add("latest")
    if "outstanding" in q or "unsatisfied" in q:
        tokens.add("outstanding")
    return tokens

def _resolve_charge_rows(question: str, charges: list[dict]) -> list[dict]:
    reference = resolve_charge_reference(question, charges)
    if reference is not None:
        return [reference]
    return charges


def load_charge_facts() -> list[dict]:
    if CHARGE_FACTS_PATH.exists():
        payload = json.loads(CHARGE_FACTS_PATH.read_text(encoding="utf-8"))
        facts = payload.get("facts") or payload.get("charges") or payload
        if isinstance(facts, list):
            return [normalize_charge_fact(fact) for fact in facts if isinstance(fact, dict)]
    return [
        {
            "workspaceId": "gails-limited",
            "chargeCode": charge["charge_code"].replace(" ", ""),
            "displayCode": charge["charge_code"],
            "shortCode": charge["charge_code"].replace(" ", "")[-4:],
            "createdDate": charge["created_date"],
            "status": charge["status"],
            "holder": charge["holder"],
            "sourceId": charge["source_document_id"],
            "sourcePage": charge["source_page"],
            "sourceQuote": charge["source_quote"],
            "reviewed": True,
            "fieldReview": {"holder": True, "createdDate": True, "status": True},
        }
        for charge in rows("SELECT * FROM charges ORDER BY created_date DESC")
    ]


def normalize_charge_fact(fact: dict) -> dict:
    normalized = dict(fact)
    if not normalized.get("displayCode") and normalized.get("displayChargeCode"):
        normalized["displayCode"] = normalized["displayChargeCode"]
    if not normalized.get("shortCode") and normalized.get("chargeCode"):
        normalized["shortCode"] = str(normalized["chargeCode"])[-4:]
    return normalized


def answer_charges(question: str = "") -> StructuredAnswer:
    facts = sorted(load_charge_facts(), key=lambda fact: str(fact.get("createdDate") or ""), reverse=True)
    if not facts:
        return StructuredAnswer(answer="I cannot identify registered charges from the dataroom.", answer_type="unknown", missing_information=["charges"], confidence="low")
    field_intent = detect_charge_field_intent(question)
    charge = resolve_charge_reference(question, facts)
    if field_intent == "list_charges":
        return answer_charge_list(facts)
    fact_key = CHARGE_FIELD_TO_FACT_KEY.get(field_intent)
    if charge is None and fact_key and all(charge_field_is_reviewed(fact, fact_key) and fact.get(fact_key) not in (None, "") for fact in facts):
        return answer_reviewed_charge_field_multiple(facts, field_intent, fact_key)
    if charge is None:
        return answer_missing_charge_reference(field_intent, facts)
    if fact_key and charge_field_is_reviewed(charge, fact_key) and charge.get(fact_key) not in (None, ""):
        return answer_reviewed_charge_field(charge, field_intent, fact_key)
    return answer_unavailable_charge_field(charge, field_intent)


def detect_charge_field_intent(question: str) -> str:
    q = question.lower()
    if re.search(r"\bwhat\s+(?:is|was|are|were)?\s*(?:the\s+)?(?:specific\s+)?charge\s+\d{4}\s+for\b", q):
        return "charge_instrument_summary"
    if re.search(r"\bwhat\s+(?:is|was)\s+(?:the\s+)?(?:specific\s+)?charge\s+for\b", q):
        return "charge_instrument_summary"
    if any(term in q for term in ["what charges", "which charges", "registered charges", "list charges", "charges registered", "charges are registered", "lenders or charges"]):
        return "list_charges"
    if any(term in q for term in ["who holds", "holder", "held by", "person entitled", "persons entitled", "lender", "security trustee"]):
        return "charge_holder"
    if any(term in q for term in ["status", "outstanding", "satisfied"]):
        return "charge_status"
    if any(term in q for term in ["when", "created", "creation date", "dated"]):
        return "charge_created_date"
    if "delivered" in q:
        return "charge_delivered_date"
    if "satisfied" in q or "satisfaction" in q:
        return "charge_satisfied_date"
    if any(term in q for term in ["short particulars", "particulars", "property charged", "charged property"]):
        return "charge_short_particulars"
    if any(term in q for term in ["assets", "secured asset", "covered", "cover", "all assets", "undertaking", "bank accounts", "shares", "real estate", "intellectual property"]):
        return "secured_assets"
    if any(term in q for term in ["fixed", "floating", "security type", "type of security"]):
        return "security_type"
    if any(term in q for term in ["obligations", "secured obligations", "liabilities secured"]):
        return "obligations_secured"
    if any(term in q for term in ["instrument", "debenture", "what does the charge say", "charge document"]):
        return "charge_instrument_summary"
    if "description" in q:
        return "charge_description"
    return "list_charges"


def resolve_charge_reference(question: str, charges: list[dict]) -> dict | None:
    q = question.lower()
    compact_q = "".join(ch for ch in q if ch.isalnum())
    for charge in charges:
        code = str(charge.get("chargeCode") or charge.get("charge_code") or "").lower().replace(" ", "")
        display = str(charge.get("displayCode") or "").lower().replace(" ", "")
        short = str(charge.get("shortCode") or code[-4:]).lower()
        if code and code in compact_q:
            return charge
        if display and display in compact_q:
            return charge
        if short and re.search(rf"(?<!\d){re.escape(short)}(?!\d)", q):
            return charge
    for charge in charges:
        year = str(charge.get("createdDate") or charge.get("created_date") or "")[:4]
        if year and year in q:
            return charge
    if "latest" in q or "newest" in q or "most recent" in q:
        return charges[0]
    if len(charges) == 1:
        return charges[0]
    return None


def answer_charge_list(facts: list[dict]) -> StructuredAnswer:
    used=[]; cites=[]; parts=[]
    for fact in facts:
        src = source_by_id(str(fact.get("sourceId")))
        if src is None:
            return unknown_answer([f"manifest source {fact.get('sourceId')}"], "I cannot answer charges because the supporting source is not in the manifest.")
        code = fact.get("displayCode") or fact.get("chargeCode")
        parts.append(f"Charge {code} was created on {fact.get('createdDate')}; status {fact.get('status')}; holder/person entitled: {fact.get('holder')}.")
        used.append(charge_fact_payload(fact, "list_charges"))
        cites.append(citation(src, str(fact.get("sourceQuote") or ""), fact.get("sourcePage")))
    return StructuredAnswer(answer=" ".join(parts), answer_type="charges_security", facts_used=used, citations=cites, confidence="high", field_intent="list_charges")


def answer_reviewed_charge_field(charge: dict, field_intent: str, fact_key: str) -> StructuredAnswer:
    src = source_by_id(str(charge.get("sourceId")))
    if src is None:
        return unknown_answer([f"manifest source {charge.get('sourceId')}"], "I cannot answer charges because the supporting source is not in the manifest.")
    value = charge.get(fact_key)
    code = charge.get("displayCode") or charge.get("chargeCode")
    if field_intent == "charge_holder":
        answer = f"Charge {code} is listed with {value} as the person entitled / charge holder."
    elif field_intent == "charge_status":
        answer = f"Charge {code} was created on {charge.get('createdDate')} and is listed as {value}."
    elif field_intent == "charge_created_date":
        answer = f"Charge {code} was created on {value}."
    else:
        answer = f"The reviewed {CHARGE_FIELD_LABELS[field_intent]} for charge {code} is: {str(value).rstrip('.')}."
    return StructuredAnswer(answer=answer, answer_type="charges_security", facts_used=[charge_fact_payload(charge, field_intent, fact_key)], citations=[citation(src, str(charge.get("sourceQuote") or ""), charge.get("sourcePage"))], confidence="high", field_intent=field_intent, resolved_charge_code=str(charge.get("chargeCode") or ""))


def answer_reviewed_charge_field_multiple(facts: list[dict], field_intent: str, fact_key: str) -> StructuredAnswer:
    used: list[dict] = []
    cites: list[Citation] = []
    parts: list[str] = []
    for fact in facts:
        src = source_by_id(str(fact.get("sourceId")))
        if src is None:
            return unknown_answer([f"manifest source {fact.get('sourceId')}"], "I cannot answer charges because the supporting source is not in the manifest.")
        code = fact.get("displayCode") or fact.get("chargeCode")
        value = str(fact.get(fact_key) or "").rstrip(".")
        parts.append(f"Charge {code}: {value}.")
        used.append(charge_fact_payload(fact, field_intent, fact_key))
        cites.append(citation(src, str(fact.get("sourceQuote") or ""), fact.get("sourcePage")))
    return StructuredAnswer(
        answer=f"Reviewed {CHARGE_FIELD_LABELS[field_intent]} for the matching charges: " + " ".join(parts),
        answer_type="charges_security",
        facts_used=used,
        citations=cites,
        confidence="high",
        field_intent=field_intent,
    )


def answer_unavailable_charge_field(charge: dict, field_intent: str) -> StructuredAnswer:
    src = source_by_id(str(charge.get("sourceId")))
    label = CHARGE_FIELD_LABELS.get(field_intent, "requested charge field")
    code = charge.get("displayCode") or charge.get("chargeCode")
    metadata = f"It does contain reviewed metadata showing charge {code} was created on {charge.get('createdDate')}, is {charge.get('status')}, and is held by {charge.get('holder')}."
    if field_intent in LEGAL_FIELD_INTENTS:
        answer = f"The current dataroom does not contain a reviewed {label} for charge {code}. {metadata} The underlying charge instrument text needs to be processed and reviewed before that field can be answered."
        missing = [f"{label} has not been extracted from the reviewed charge instrument"]
    else:
        answer = f"The current dataroom does not contain a reviewed {label} for charge {code}."
        missing = [f"{label} is not available in reviewed charge facts"]
    cites = [citation(src, str(charge.get("sourceQuote") or ""), charge.get("sourcePage"))] if src else []
    return StructuredAnswer(answer=answer, answer_type="charges_security", facts_used=[charge_fact_payload(charge, field_intent)], citations=cites, missing_information=missing, confidence="low", field_intent=field_intent, resolved_charge_code=str(charge.get("chargeCode") or ""))


def answer_missing_charge_reference(field_intent: str, facts: list[dict]) -> StructuredAnswer:
    label = CHARGE_FIELD_LABELS.get(field_intent, "requested charge field")
    parts = [f"charge {fact.get('displayCode') or fact.get('chargeCode')} ({fact.get('createdDate')})" for fact in facts]
    cites=[]
    for fact in facts:
        src = source_by_id(str(fact.get("sourceId")))
        if src:
            cites.append(citation(src, str(fact.get("sourceQuote") or ""), fact.get("sourcePage")))
    if field_intent in LEGAL_FIELD_INTENTS:
        answer = (
            f"The current dataroom does not contain reviewed {label} fields for the registered charges in scope ({'; '.join(parts)}). "
            "It only contains reviewed Companies House metadata for charge code, created date, status, and holder/person entitled; "
            "the underlying charge instrument text needs to be processed and reviewed before that field can be answered."
        )
        missing = [f"{label} has not been extracted from the reviewed charge instrument"]
    else:
        answer = (
            f"There are multiple registered charges in the dataroom ({'; '.join(parts)}). "
            f"I cannot give a single grounded {label} answer without a specific charge reference."
        )
        missing = [f"Specify a charge code or year for {label}"]
    return StructuredAnswer(answer=answer, answer_type="charges_security", facts_used=[charge_fact_payload(fact, field_intent) for fact in facts], citations=cites, missing_information=missing, confidence="low", field_intent=field_intent)


def charge_field_is_reviewed(charge: dict, fact_key: str) -> bool:
    review = charge.get("fieldReview") if isinstance(charge.get("fieldReview"), dict) else {}
    return bool(charge.get("reviewed") and review.get(fact_key))


def charge_fact_payload(charge: dict, field_intent: str, fact_key: str | None = None) -> dict:
    payload = dict(charge)
    payload["fieldIntent"] = field_intent
    if fact_key:
        payload["requestedField"] = fact_key
    return payload

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
