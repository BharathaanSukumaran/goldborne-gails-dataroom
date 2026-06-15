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
  fieldIntent?: string;
  field_intent?: string;
  resolvedChargeCode?: string;
  resolved_charge_code?: string;
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
const CHARGE_FIELD_REQUEST_TERMS = ["asset", "assets", "collateral", "cover", "covers", "covered", "description", "describe", "fixed charge", "floating charge", "secured over", "security covers", "security package", "what security"];
const CHARGE_DESCRIPTIVE_TERMS = ["asset", "assets", "collateral", "debenture", "description", "fixed charge", "fixed and floating", "floating charge", "property", "secured over", "security covers", "security package", "undertaking"];
const CHARGE_FIELD_TERMS = [
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
  "satisfied"
];
const CHARGE_FIELD_LABELS: Record<string, string> = {
  list_charges: "registered charges",
  charge_holder: "charge holder",
  charge_status: "charge status",
  charge_created_date: "charge created date",
  charge_delivered_date: "charge delivered date",
  charge_satisfied_date: "charge satisfied date",
  charge_description: "charge description",
  charge_short_particulars: "short particulars",
  secured_assets: "secured assets",
  security_type: "security type",
  obligations_secured: "obligations secured",
  charge_instrument_summary: "charge instrument summary"
};
const LEGAL_CHARGE_FIELD_INTENTS = new Set([
  "charge_description",
  "charge_short_particulars",
  "secured_assets",
  "security_type",
  "obligations_secured",
  "charge_instrument_summary"
]);
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
    return Response.json(structuredChargesAnswer(question));
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
  if (isChargeQuestion(q)) return "charges_security";
  if (FINANCIAL_TERMS.some((term) => q.includes(term))) return "financial_metric";
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
  if (route === "charges_security" || isChargeQuestion(q)) facts.push(...resolveChargeFacts(question, chargeFacts));
  if (route === "ownership_management" || OWNERSHIP_TERMS.some((term) => q.includes(term))) facts.push(...ownershipFacts, ...officerFacts);

  return facts;
}

function isChargeQuestion(q: string): boolean {
  if (CHARGES_TERMS.some((term) => q.includes(term))) return true;
  const hasChargeFieldIntent = CHARGE_FIELD_TERMS.some((term) => q.includes(term));
  const hasChargeReference = chargeReferenceTokens(q).size > 0;
  return hasChargeFieldIntent && hasChargeReference;
}

function chargeReferenceTokens(q: string): Set<string> {
  const tokens = new Set<string>();
  const compact = q.replace(/[^a-z0-9]/g, "");
  for (const suffix of ["0005", "0006"]) {
    if (q.includes(suffix) || compact.includes(`06055393${suffix}`)) tokens.add(suffix);
  }
  for (const year of ["2021", "2022"]) {
    if (q.includes(year)) tokens.add(year);
  }
  if (q.includes("latest") || q.includes("newest") || q.includes("most recent")) tokens.add("latest");
  if (q.includes("outstanding") || q.includes("unsatisfied")) tokens.add("outstanding");
  return tokens;
}

type ChargeFact = (typeof chargeFacts)[number];

function resolveChargeFacts(question: string, facts: ChargeFact[]): ChargeFact[] {
  const tokens = chargeReferenceTokens(question.toLowerCase());
  if (!tokens.size) return facts;

  let selected = facts;
  const codeTokens = ["0005", "0006"].filter((token) => tokens.has(token));
  if (codeTokens.length) {
    selected = selected.filter((fact) => codeTokens.some((token) => fact.chargeCode.replace(/\s/g, "").endsWith(token)));
  }

  const yearTokens = ["2021", "2022"].filter((token) => tokens.has(token));
  if (yearTokens.length) {
    selected = selected.filter((fact) => yearTokens.includes(String(fact.createdDate || "").slice(0, 4)));
  }

  if (tokens.has("outstanding")) {
    selected = selected.filter((fact) => fact.status.toLowerCase() === "outstanding");
  }

  if (tokens.has("latest")) {
    selected = selected.slice(0, 1);
  }

  return selected;
}

function structuredChargesAnswer(question: string): AskResponse {
  const allFacts = chargeFacts
    .filter((fact) => sourceExists(factSourceId(fact) || ""))
    .sort((a, b) => String(b.createdDate).localeCompare(String(a.createdDate)));
  if (!allFacts.length) return unknown(["charges"]);

  const fieldIntent = detectChargeFieldIntent(question);
  const facts = resolveChargeFacts(question, allFacts);
  if (!facts.length) return unknown(["matching charge reference"], "I cannot resolve that charge reference from the dataroom.");

  if (fieldIntent === "list_charges") return answerChargeList(facts);
  if (facts.length !== 1) return answerMissingChargeReference(fieldIntent, facts);

  const charge = facts[0];
  if (fieldIntent === "charge_holder") {
    return chargeFieldResponse(charge, fieldIntent, `Charge ${charge.chargeCode} is listed with ${charge.holder} as the person entitled / charge holder.`, "high");
  }
  if (fieldIntent === "charge_status") {
    return chargeFieldResponse(charge, fieldIntent, `Charge ${charge.chargeCode} is listed as ${charge.status}.`, "high");
  }
  if (fieldIntent === "charge_created_date") {
    return chargeFieldResponse(charge, fieldIntent, `Charge ${charge.chargeCode} was created on ${charge.createdDate}.`, "high");
  }
  return unavailableChargeFieldResponse(charge, fieldIntent);
}

function detectChargeFieldIntent(question: string): string {
  const q = question.toLowerCase();
  if (["what charges", "which charges", "registered charges", "list charges", "charges registered", "charges are registered", "lenders or charges"].some((term) => q.includes(term))) return "list_charges";
  if (["who holds", "holder", "held by", "person entitled", "persons entitled", "lender", "security trustee"].some((term) => q.includes(term))) return "charge_holder";
  if (["status", "outstanding", "satisfied"].some((term) => q.includes(term))) return "charge_status";
  if (["when", "created", "creation date", "dated"].some((term) => q.includes(term))) return "charge_created_date";
  if (q.includes("delivered")) return "charge_delivered_date";
  if (q.includes("satisfaction")) return "charge_satisfied_date";
  if (["short particulars", "particulars", "property charged", "charged property"].some((term) => q.includes(term))) return "charge_short_particulars";
  if (["assets", "secured asset", "covered", "cover", "all assets", "undertaking", "bank accounts", "shares", "real estate", "intellectual property"].some((term) => q.includes(term))) return "secured_assets";
  if (["fixed", "floating", "security type", "type of security"].some((term) => q.includes(term))) return "security_type";
  if (["obligations", "secured obligations", "liabilities secured"].some((term) => q.includes(term))) return "obligations_secured";
  if (["instrument", "debenture", "what does the charge say", "charge document"].some((term) => q.includes(term))) return "charge_instrument_summary";
  if (q.includes("description")) return "charge_description";
  return "list_charges";
}

function answerChargeList(facts: ChargeFact[]): AskResponse {
  return makeResponse({
    answer: facts
      .map((fact) => "Charge " + fact.chargeCode + " was created on " + fact.createdDate + "; status " + fact.status + "; holder/person entitled: " + fact.holder + ".")
      .join(" "),
    answerType: "charges_security",
    factsUsed: facts.map((fact) => chargeFactPayload(fact, "list_charges")),
    citations: dedupeCitations(facts.map((fact) => citation(fact.sourceId, fact.sourceQuote, null))),
    missingInformation: [],
    confidence: "high",
    fieldIntent: "list_charges"
  });
}

function chargeFieldResponse(charge: ChargeFact, fieldIntent: string, answer: string, confidence: Confidence): AskResponse {
  return makeResponse({
    answer,
    answerType: "charges_security",
    factsUsed: [chargeFactPayload(charge, fieldIntent)],
    citations: [citation(charge.sourceId, charge.sourceQuote, null)],
    missingInformation: [],
    confidence,
    fieldIntent,
    resolvedChargeCode: charge.chargeCode
  });
}

function unavailableChargeFieldResponse(charge: ChargeFact, fieldIntent: string): AskResponse {
  const label = CHARGE_FIELD_LABELS[fieldIntent] || "requested charge field";
  const metadata = `It does contain reviewed metadata showing charge ${charge.chargeCode} was created on ${charge.createdDate}, is ${charge.status}, and is held by ${charge.holder}.`;
  const answer = LEGAL_CHARGE_FIELD_INTENTS.has(fieldIntent)
    ? `The current dataroom does not contain a reviewed ${label} for charge ${charge.chargeCode}. ${metadata} The underlying charge instrument text needs to be processed and reviewed before that field can be answered.`
    : `The current dataroom does not contain a reviewed ${label} for charge ${charge.chargeCode}.`;
  const missingInformation = LEGAL_CHARGE_FIELD_INTENTS.has(fieldIntent)
    ? [`${label} has not been extracted from the reviewed charge instrument`]
    : [`${label} is not available in reviewed charge facts`];
  return makeResponse({
    answer,
    answerType: "charges_security",
    factsUsed: [chargeFactPayload(charge, fieldIntent)],
    citations: [citation(charge.sourceId, charge.sourceQuote, null)],
    missingInformation,
    confidence: "low",
    fieldIntent,
    resolvedChargeCode: charge.chargeCode
  });
}

function answerMissingChargeReference(fieldIntent: string, facts: ChargeFact[]): AskResponse {
  const label = CHARGE_FIELD_LABELS[fieldIntent] || "requested charge field";
  const parts = facts.map((fact) => `charge ${fact.chargeCode} (${fact.createdDate})`).join("; ");
  const answer = LEGAL_CHARGE_FIELD_INTENTS.has(fieldIntent)
    ? `The current dataroom does not contain reviewed ${label} fields for the registered charges in scope (${parts}). It only contains reviewed Companies House metadata for charge code, created date, status, and holder/person entitled; the underlying charge instrument text needs to be processed and reviewed before that field can be answered.`
    : `There are multiple registered charges in the dataroom (${parts}). I cannot give a single grounded ${label} answer without a specific charge reference.`;
  const missingInformation = LEGAL_CHARGE_FIELD_INTENTS.has(fieldIntent)
    ? [`${label} has not been extracted from the reviewed charge instrument`]
    : [`Specify a charge code or year for ${label}`];
  return makeResponse({
    answer,
    answerType: "charges_security",
    factsUsed: facts.map((fact) => chargeFactPayload(fact, fieldIntent)),
    citations: dedupeCitations(facts.map((fact) => citation(fact.sourceId, fact.sourceQuote, null))),
    missingInformation,
    confidence: "low",
    fieldIntent
  });
}

function chargeFactPayload(charge: ChargeFact, fieldIntent: string): Record<string, unknown> {
  return { ...charge, fieldIntent };
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

  if (response.answerType === "charges_security" && hasUnsupportedChargeFieldClaim(response, evidence)) return false;
  return true;
}


function isSpecificChargeFieldQuestion(question: string): boolean {
  const q = question.toLowerCase();
  return CHARGE_FIELD_REQUEST_TERMS.some((term) => q.includes(term));
}

function hasSupportedChargeFieldDetails(facts: unknown[]): boolean {
  return facts.some((fact) => supportedChargeFieldText(fact).trim().length > 0);
}

function hasUnsupportedChargeFieldClaim(response: AskResponse, evidence: EvidencePacket): boolean {
  const answer = response.answer.toLowerCase();
  const claimedTerms = CHARGE_DESCRIPTIVE_TERMS.filter((term) => answer.includes(term));
  if (!claimedTerms.length) return false;

  const supported = evidence.structuredFacts.map(supportedChargeFieldText).join(" ").toLowerCase();
  return claimedTerms.some((term) => !supported.includes(term));
}

function supportedChargeFieldText(fact: unknown): string {
  if (!isRecord(fact)) return "";
  return [
    fact.description,
    fact.classification,
    fact.assets,
    fact.assetDescription,
    fact.asset_description,
    fact.security,
    fact.securityDescription,
    fact.security_description
  ].filter((value): value is string => typeof value === "string" && value.trim().length > 0).join(" ");
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

function makeResponse(input: Omit<AskResponse, "answer_type" | "facts_used" | "missing_information" | "field_intent" | "resolved_charge_code">): AskResponse {
  return {
    ...input,
    answer_type: input.answerType,
    facts_used: input.factsUsed,
    missing_information: input.missingInformation,
    field_intent: input.fieldIntent,
    resolved_charge_code: input.resolvedChargeCode
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
