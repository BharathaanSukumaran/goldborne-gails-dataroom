from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

class Citation(BaseModel):
    source_id: str
    title: str
    category: str
    source_url: str
    page: int | None = None
    snippet: str | None = None

class AskRequest(BaseModel):
    workspaceId: str | None = None
    question: str = Field(min_length=1)

class StructuredAnswer(BaseModel):
    answer: str
    answer_type: Literal["structured", "retrieval", "hybrid", "financial_metric", "charges_security", "ownership_management", "credit_summary", "source_lookup", "unknown", "other"]
    facts_used: list[dict] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    field_intent: str | None = None
    resolved_charge_code: str | None = None

class EvalCaseResult(BaseModel):
    question: str
    passed: bool
    answer_type: str
    notes: list[str] = Field(default_factory=list)

class EvalRunResponse(BaseModel):
    passed: bool
    results: list[EvalCaseResult]
