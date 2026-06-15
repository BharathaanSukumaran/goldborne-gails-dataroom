import type { Config, Context } from "@netlify/functions";
import OpenAI from "openai";
import {
  chargeFacts,
  citation,
  financialFacts,
  officerFacts,
  ownershipFacts,
  retrieveSourceChunks,
  sourceExists,
  type Citation,
  type SourceChunk
} from "./_shared/data";

type AnswerType = "financial_metric" | "charges_security" | "ownership_management" | "credit_summary" | "source_lookup" | "unknown" | "other";
type Confidence = "high" | "medium" | "low";

type AskPayload = {
  workspaceId?: string;
  question?: unknown;
};

type AskResponse = {
  answer: string;
  answerType: AnswerType;
  answer_type: AnswerType;
  citations: Citation[];
  factsUsed: unknown[];
  facts_used: unknown[];
  missingInformation: string[];
  missing_information: string[];
  confidence: Confidence;
};

type EvidencePacket = {
  sourceChunks: SourceChunk[];
  structuredFacts: unknown[];
};

const MODEL = process.env.OPENAI_MODEL || "gpt-4.1-mini";
const OPENAI_SYNTHESIS_ENABLED = process.env.USE_OPENAI_SYNTHESIS === "true";
const NOT_AVAILABLE = "This is not available in the current dataroom.";
const FINANCIAL_TERMS = ["revenue", "turnover", "ebitda", "profit", "debt", "cash", "assets", "liabilities", "borrowings"];
const CHARGES_TERMS = ["charge", "charges", "security", "lender", "persons entitled"];
const OWNERSHIP_TERMS = ["owner", "ownership", "psc", "shareholder", "director", "directors", "management", "officer", "officers", "manage", "manages"];
const SOURCE_TERMS = ["source", "sources", "document", "documents", "filing", "filings", "dataroom", "missing information"];
const CREDIT_TERMS = ["credit", "committee", "risk", "risks", "summary", "summarise", "summarize", "business"];

const SYSTEM_PROMPT = [
  "You are a credit analyst assistant for Goldborne Capital.",
  "Answer only using the supplied dataroom source excerpts and structured facts.",
  "If the supplied evidence does not support the answer, say it is not available in the current dataroom and list missingInformation.",
  "Do not invent figures, lenders, ownership, charges, dates, covenants, page references, or source ids.",
  "Never estimate EBITDA. If it is not reported or cannot be computed from supplied facts, say it is unavailable.",
  "Return strict JSON with keys: answer, answerType, citations, factsUsed, missingInformation, confidence.",
  "Every citation must use a sourceId from the supplied source excerpts or structured facts."
].join(" ");

const responseSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    answer: { type: "string" },
    answerType: {
      type: "string",
      enum: ["financial_metric", "charges_security", "ownership_management", "credit_summary", "source_lookup", "unknown", "other"]
    },
    citations: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        properties: {
          sourceId: { type: "string" },
          title: { type: "string" },
          page: { anyOf: [{ type: "number" }, { type: "null" }] },
          snippet: { type: "string" }
        },
        required: ["sourceId", "title", "page", "snippet"]
      }
    },
    factsUsed: { type: "array", items: { type: "string" } },
    missingInformation: { type: "array", items: { type: "string" } },
    confidence: { type: "string", enum: ["high", "medium", "low"] }
  },
  required: ["answer", "answerType", "citations", "factsUsed", "missingInformation", "confidence"]
} as const;

export default async (req: Request, _context: Context) => {
  if (req.method !== "POST") return Response.json({ detail: "Method not allowed" }, { status: 405 });

  const body = (await req.json().catch(() => ({}))) as AskPayload;
  if (!body.question || typeof body.question !== "string") {
    return Response.json(unknown(["question"]));
  }

  const question = body.question.trim();
  const route = classifyQuestion(question);
  const evidence = buildEvidence(question, route);

  if (route === "unknown" || route === "other") {
    return Response.json(unknown(["supported dataroom question"]));
  }

  if (route === "financial_metric" && !hasUsableFinancialValue(evidence)) {
    return Response.json(unknown(["reviewed usable financial_facts"]));
  }

  if (route === "charges_security") {
    return Response.json(structuredChargesAnswer());
  }

  if (route === "ownership_management") {
    return Response.json(structuredOwnershipAnswer());
  }

  if (!OPENAI_SYNTHESIS_ENABLED || !process.env.OPENAI_API_KEY) {
    if (route === "source_lookup" && evidence.sourceChunks.length) {
      return Response.json(snippetOnlyAnswer(route, evidence));
    }
    const missing = [
      ...(!OPENAI_SYNTHESIS_ENABLED ? ["USE_OPENAI_SYNTHESIS=true"] : []),
      ...(!process.env.OPENAI_API_KEY ? ["OPENAI_API_KEY"] : [])
    ];
    return Response.json(unknown(missing, "OpenAI synthesis is not configured. Set USE_OPENAI_SYNTHESIS=true and OPENAI_API_KEY in the Netlify server environment to enable dataroom answers."));
  }

  if (!evidence.sourceChunks.length && !evidence.structuredFacts.length) {
    return Response.json(unknown(["retrieved manifest-backed evidence"]));
  }

  try {
    const answer = await synthesizeAnswer(question, route, evidence);
    return Response.json(answer);
  } catch (error) {
    console.error("OpenAI Responses API request failed", error);
    return Response.json(unknown(["OpenAI Responses API completion"], "The dataroom answer service could not complete OpenAI synthesis. Try again after checking the server OpenAI configuration."), { status: 502 });
  }
};

export const config: Config = { path: "/api/ask" };

function classifyQuestion(question: string): AnswerType {
  const q = question.toLowerCase();
  if (["covenant", "headroom", "private banking", "facility agreement"].some((term) => q.includes(term))) return "unknown";
  if (FINANCIAL_TERMS.some((term) => q.includes(term))) return "financial_metric";
  if (CHARGES_TERMS.some((term) => q.includes(term))) return "charges_security";
  if (OWNERSHIP_TERMS.some((term) => q.includes(term))) return "ownership_management";
  if (CREDIT_TERMS.some((term) => q.includes(term))) return "credit_summary";
  if (SOURCE_TERMS.some((term) => q.includes(term))) return "source_lookup";
  return "other";
}

function buildEvidence(question: string, route: AnswerType): EvidencePacket {
  const retrieved = retrieveSourceChunks(question, 8).filter((chunk) => sourceExists(chunk.sourceId) && chunk.text.trim());
  const structuredFacts = relevantStructuredFacts(question, route).filter((fact) => {
    const sourceId = factSourceId(fact);
    return Boolean(sourceId && sourceExists(sourceId));
  });
  const factSourceIds = new Set(structuredFacts.map((fact) => factSourceId(fact)).filter((sourceId): sourceId is string => Boolean(sourceId)));
  const factChunks = Array.from(factSourceIds).flatMap((sourceId) => retrieveSourceChunks(sourceId, 2)).filter((chunk) => sourceExists(chunk.sourceId));
  return {
    sourceChunks: dedupeChunks([...retrieved, ...factChunks]).slice(0, 10),
    structuredFacts
  };
}

function relevantStructuredFacts(question: string, route: AnswerType): unknown[] {
  const q = question.toLowerCase();
  const facts: unknown[] = [];

  if (route === "financial_metric" || FINANCIAL_TERMS.some((term) => q.includes(term))) facts.push(...financialFacts.filter(isAnswerUsableFinancialFact));
  if (route === "charges_security" || CHARGES_TERMS.some((term) => q.includes(term))) facts.push(...chargeFacts);
  if (route === "ownership_management" || OWNERSHIP_TERMS.some((term) => q.includes(term))) facts.push(...ownershipFacts, ...officerFacts);

  return facts;
}

function structuredChargesAnswer(): AskResponse {
  const facts = chargeFacts.filter((fact) => sourceExists(factSourceId(fact) || ""));
  if (!facts.length) return unknown(["charges"]);

  return makeResponse({
    answer: facts
      .map((fact) => "Charge " + fact.chargeCode + " was created on " + fact.createdDate + "; status " + fact.status + "; holder/person entitled: " + fact.holder + ".")
      .join(" "),
    answerType: "charges_security",
    factsUsed: facts,
    citations: dedupeCitations(facts.map((fact) => citation(fact.sourceId, fact.sourceQuote, null))),
    missingInformation: [],
    confidence: "high"
  });
}

function structuredOwnershipAnswer(): AskResponse {
  const ownerFacts = ownershipFacts.filter((fact) => sourceExists(factSourceId(fact) || ""));
  const currentOfficers = officerFacts.filter((fact) => fact.status === "current" && sourceExists(factSourceId(fact) || ""));
  const facts = [...ownerFacts, ...currentOfficers];
  if (!facts.length) return unknown(["ownership/PSC", "current directors"]);

  const ownershipParts = ownerFacts.map((fact) => fact.ownerName + " is an " + fact.status + " " + fact.controlType + " with " + fact.percentageBand + " control.");
  const officerParts = currentOfficers.map((fact) => fact.name + " (" + fact.role + ")");
  const answerParts = [
    ...ownershipParts,
    officerParts.length ? "Current directors/officers in the dataroom: " + officerParts.join("; ") + "." : ""
  ].filter(Boolean);

  return makeResponse({
    answer: answerParts.join(" "),
    answerType: "ownership_management",
    factsUsed: facts,
    citations: dedupeCitations(facts.map((fact) => citation(fact.sourceId, fact.sourceQuote, null))),
    missingInformation: [],
    confidence: "high"
  });
}

async function synthesizeAnswer(question: string, route: AnswerType, evidence: EvidencePacket): Promise<AskResponse> {
  const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  const response = await client.responses.create({
    model: MODEL,
    input: [
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: buildPrompt(question, route, evidence) }
    ],
    text: {
      format: {
        type: "json_schema",
        name: "dataroom_answer",
        schema: responseSchema,
        strict: true
      }
    }
  });

  const parsed = parseModelJson(response.output_text ?? "");
  if (!parsed) return unknown(["model_json_response"]);

  const normalized = makeResponse({
    answer: String(parsed.answer || NOT_AVAILABLE),
    answerType: normalizeAnswerType(parsed.answerType, route),
    factsUsed: evidenceFactsUsed(evidence),
    citations: normalizeModelCitations(parsed.citations, evidence),
    missingInformation: Array.isArray(parsed.missingInformation) ? parsed.missingInformation.map(String) : [],
    confidence: normalizeConfidence(parsed.confidence)
  });

  return verifyResponse(normalized, evidence) ? normalized : unknown(["answer verification failed"]);
}

function buildPrompt(question: string, route: AnswerType, evidence: EvidencePacket): string {
  const financialMetricsAreUnreviewed = evidence.structuredFacts.some((fact) => {
    if (!isRecord(fact) || typeof fact.metric !== "string") return false;
    return !isAnswerUsableFinancialFact(fact);
  });

  return JSON.stringify({
    workspaceId: "gails-limited",
    route,
    question,
    sourceExcerpts: evidence.sourceChunks.map(chunkPayload),
    structuredFacts: evidence.structuredFacts,
    financialWarning: financialMetricsAreUnreviewed
      ? "Financial metric facts are not reviewed and approved for answer use. Do not state numeric revenue, EBITDA, debt, cash, assets, liabilities, or profit. Mark unavailable metrics in missingInformation."
      : undefined,
    responseRules: [
      "Use only sourceExcerpts and structuredFacts supplied in this prompt.",
      `If evidence is insufficient, answer exactly: ${NOT_AVAILABLE}`,
      "Citations must use sourceId values present in sourceExcerpts or structuredFacts.",
      "Keep factsUsed to the exact supplied facts or chunks that support the answer."
    ]
  });
}


function snippetOnlyAnswer(route: AnswerType, evidence: EvidencePacket): AskResponse {
  const chunks = evidence.sourceChunks.filter((chunk) => sourceExists(chunk.sourceId) && chunk.text.trim());
  if (!chunks.length) return unknown(["retrieved manifest-backed evidence"]);
  return makeResponse({
    answer: "Retrieved dataroom snippets state: " + chunks
      .slice(0, 3)
      .map((chunk) => `${chunk.title}: ${chunk.text.slice(0, 700).trim()}`)
      .join(" ")
      .slice(0, 1200),
    answerType: route,
    factsUsed: chunks.map(chunkPayload),
    citations: dedupeCitations(chunks.slice(0, 3).map((chunk) => citation(chunk.sourceId, chunk.text.slice(0, 260), chunk.page))),
    missingInformation: [],
    confidence: "medium"
  });
}

function evidenceFactsUsed(evidence: EvidencePacket): unknown[] {
  return [
    ...evidence.structuredFacts,
    ...evidence.sourceChunks.map(chunkPayload)
  ];
}

function verifyResponse(response: AskResponse, evidence: EvidencePacket): boolean {
  const validSourceIds = new Set([
    ...evidence.sourceChunks.map((chunk) => chunk.sourceId),
    ...evidence.structuredFacts.map((fact) => factSourceId(fact)).filter((sourceId): sourceId is string => Boolean(sourceId))
  ]);
  if (response.citations.some((item) => !validSourceIds.has(item.source_id) || !sourceExists(item.source_id))) return false;

  const mentionsFinancialMetric = /\b(revenue|turnover|ebitda|debt|borrowings|profit|cash|assets|liabilities)\b/i.test(response.answer);
  const hasCurrencyOrLargeNumber = /(£|gbp|\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b|\b\d+(?:\.\d+)?m\b)/i.test(response.answer);
  const hasSupportedFinancialValue = evidence.structuredFacts.some((fact) => isAnswerUsableFinancialFact(fact) && fact.value !== null);
  if (mentionsFinancialMetric && hasCurrencyOrLargeNumber && !hasSupportedFinancialValue) return false;

  if (/ebitda/i.test(response.answer) && hasCurrencyOrLargeNumber && !hasSupportedFinancialValue) return false;
  return true;
}

function normalizeModelCitations(value: unknown, evidence: EvidencePacket): Citation[] {
  const fallback = () => fallbackCitations(evidence);
  if (!Array.isArray(value)) return fallback();

  const validSourceIds = new Set([
    ...evidence.sourceChunks.map((chunk) => chunk.sourceId),
    ...evidence.structuredFacts.map((fact) => factSourceId(fact)).filter((sourceId): sourceId is string => Boolean(sourceId))
  ]);

  const citations = value.flatMap((item): Citation[] => {
    if (!isRecord(item)) return [];
    const sourceId = String(item.sourceId || item.source_id || "");
    if (!sourceId || !validSourceIds.has(sourceId) || !sourceExists(sourceId)) return [];
    const snippet = typeof item.snippet === "string" ? item.snippet : undefined;
    const page = typeof item.page === "number" ? item.page : null;
    return [citation(sourceId, snippet, page)];
  });

  return citations.length ? dedupeCitations(citations) : fallback();
}

function fallbackCitations(evidence: EvidencePacket): Citation[] {
  const chunkCitations = evidence.sourceChunks.slice(0, 3).map((chunk) => citation(chunk.sourceId, chunk.text.slice(0, 260), chunk.page));
  const factCitations = evidence.structuredFacts.flatMap((fact) => {
    const sourceId = factSourceId(fact);
    if (!sourceId || !sourceExists(sourceId)) return [];
    const snippet = isRecord(fact) && typeof fact.sourceQuote === "string" ? fact.sourceQuote : isRecord(fact) && typeof fact.quote === "string" ? fact.quote : undefined;
    const page = isRecord(fact) && typeof fact.page === "number" ? fact.page : null;
    return [citation(sourceId, snippet, page)];
  });
  return dedupeCitations([...chunkCitations, ...factCitations]).slice(0, 5);
}

function normalizeFactsUsed(value: unknown, fallbackFacts: unknown[]): unknown[] {
  if (!Array.isArray(value)) return fallbackFacts;
  return value.length ? value : fallbackFacts;
}

function parseModelJson(text: string): Record<string, unknown> | null {
  try {
    return JSON.parse(text) as Record<string, unknown>;
  } catch {
    const match = text.match(/\{[\s\S]*\}/);
    if (!match) return null;
    try {
      return JSON.parse(match[0]) as Record<string, unknown>;
    } catch {
      return null;
    }
  }
}

function normalizeAnswerType(value: unknown, fallback: AnswerType): AnswerType {
  if (fallback === "unknown") return "unknown";

  const allowed: AnswerType[] = ["financial_metric", "charges_security", "ownership_management", "credit_summary", "source_lookup", "unknown", "other"];
  return allowed.includes(value as AnswerType) ? value as AnswerType : fallback;
}

function normalizeConfidence(value: unknown): Confidence {
  return value === "high" || value === "medium" || value === "low" ? value : "medium";
}

function chunkPayload(chunk: SourceChunk) {
  return {
    chunkId: chunk.chunkId,
    sourceId: chunk.sourceId,
    title: chunk.title,
    category: chunk.category,
    page: chunk.page,
    snippet: chunk.text.slice(0, 700)
  };
}

function dedupeChunks(chunks: SourceChunk[]): SourceChunk[] {
  const seen = new Set<string>();
  const out: SourceChunk[] = [];
  for (const chunk of chunks) {
    if (seen.has(chunk.chunkId)) continue;
    seen.add(chunk.chunkId);
    out.push(chunk);
  }
  return out;
}

function dedupeCitations(citations: Citation[]): Citation[] {
  const seen = new Set<string>();
  const out: Citation[] = [];
  for (const item of citations) {
    const key = `${item.source_id}:${item.page ?? ""}:${item.snippet ?? ""}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
}

function hasUsableFinancialValue(evidence: EvidencePacket): boolean {
  return evidence.structuredFacts.some((fact) => isAnswerUsableFinancialFact(fact) && fact.value !== null);
}

function isAnswerUsableFinancialFact(fact: unknown): fact is Record<string, unknown> {
  return isRecord(fact) && typeof fact.metric === "string" && fact.reviewed === true && fact.usedInAnswers === true;
}

function factSourceId(fact: unknown): string | null {
  return isRecord(fact) && typeof fact.sourceId === "string" ? fact.sourceId : null;
}

function unknown(missingInformation: string[], answer = NOT_AVAILABLE): AskResponse {
  return makeResponse({
    answer,
    answerType: "unknown",
    factsUsed: [],
    citations: [],
    missingInformation,
    confidence: "low"
  });
}

function makeResponse(input: Omit<AskResponse, "answer_type" | "facts_used" | "missing_information">): AskResponse {
  return {
    ...input,
    answer_type: input.answerType,
    facts_used: input.factsUsed,
    missing_information: input.missingInformation
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
