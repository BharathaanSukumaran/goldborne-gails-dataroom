import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

export type ManifestSource = {
  source_id: string;
  sourceId?: string;
  workspaceId?: string;
  title: string;
  category: string;
  issuer: string;
  retrieved_at: string;
  retrievedAt?: string;
  source_url: string;
  url?: string;
  local_path: string;
  localPath?: string;
  processed_path?: string;
  processedPath?: string;
  snippet?: string;
  indexed?: boolean;
  included_reason: string;
  includedReason?: string;
  processing_status: string;
  source_status?: string;
  status?: string;
  notes?: string | null;
  pages?: number | null;
};

export type DataroomManifest = {
  company: Record<string, unknown>;
  coverage?: Record<string, unknown>;
  sources: ManifestSource[];
};

export type SourceChunk = {
  chunkId: string;
  sourceId: string;
  title: string;
  category: string;
  page: number | null;
  text: string;
  score?: number;
};

export type Citation = {
  source_id: string;
  sourceId: string;
  title: string;
  category: string;
  source_url: string;
  url: string;
  page: number | null;
  snippet?: string;
};

export type FinancialFact = {
  workspaceId: string;
  metric: "revenue" | "EBITDA" | "debt";
  periodEnd: string;
  value: string | null;
  currency: "GBP";
  unit: "GBP";
  reportedOrComputed: "reported" | "computed" | "unknown" | "unavailable";
  formula?: string | null;
  sourceId: string;
  page: number | null;
  quote: string;
  reviewed: boolean;
  usedInAnswers: boolean;
};

const WORKSPACE_ID = "gails-limited";
const PROJECT_ROOT = findProjectRoot();
const MANIFEST_PATH = join(PROJECT_ROOT, "dataroom", "manifest.json");
const PROCESSED_DIR = join(PROJECT_ROOT, "dataroom", "processed");

const processedPathBySourceId: Record<string, string> = {
  "ch-profile-06055393": "ch_profile_06055393.md",
  "ch-filing-history-06055393": "ch_filing_history_06055393.md",
  "ch-charges-register-06055393": "ch_charges_register.md",
  "ch-charge-0006": "ch_charge_0006.md",
  "ch-charge-0005": "ch_charge_0005.md",
  "ch-officers-06055393": "ch_officers_06055393.md",
  "ch-psc-06055393": "ch_psc_06055393.md",
  "news-expansion-2025-placeholder": "guardian_expansion_2025.md",
  "news-community-context-2024-placeholder": "guardian_community_2024.md"
};

export const financialFacts: FinancialFact[] = ["revenue", "EBITDA", "debt"].map((metric) => ({
  workspaceId: WORKSPACE_ID,
  metric: metric as FinancialFact["metric"],
  periodEnd: "2025-02-28",
  value: null,
  currency: "GBP",
  unit: "GBP",
  reportedOrComputed: "unavailable",
  sourceId: "ch-parent-accounts-2025",
  page: null,
  quote: "Financial value unavailable until the source accounts PDF is ingested and human-reviewed.",
  reviewed: false,
  usedInAnswers: false
}));

export const chargeFacts = [
  {
    workspaceId: WORKSPACE_ID,
    chargeCode: "0605 5393 0006",
    createdDate: "2022-06-06",
    status: "outstanding",
    holder: "Glas Trust Corporation Limited",
    sourceId: "ch-charge-0006",
    sourceQuote: "Companies House charges metadata records this charge as outstanding and held by Glas Trust Corporation Limited."
  },
  {
    workspaceId: WORKSPACE_ID,
    chargeCode: "0605 5393 0005",
    createdDate: "2021-11-04",
    status: "outstanding",
    holder: "Glas Trust Corporation Limited",
    sourceId: "ch-charge-0005",
    sourceQuote: "Companies House charges metadata records this charge as outstanding and held by Glas Trust Corporation Limited."
  }
];

export const officerFacts = [
  { workspaceId: WORKSPACE_ID, name: "Nicholas John Ayerst", role: "Director", status: "current", sourceId: "ch-officers-06055393", sourceQuote: "Companies House officers metadata." },
  { workspaceId: WORKSPACE_ID, name: "Thomas Ralph Molnar", role: "Director", status: "current", sourceId: "ch-officers-06055393", sourceQuote: "Companies House officers metadata." },
  { workspaceId: WORKSPACE_ID, name: "Andy Trigwell", role: "Director", status: "current", sourceId: "ch-officers-06055393", sourceQuote: "Companies House officers metadata." }
];

export const ownershipFacts = [
  {
    workspaceId: WORKSPACE_ID,
    ownerName: "Bread Limited",
    controlType: "person with significant control",
    percentageBand: "75% or more",
    status: "active",
    sourceId: "ch-psc-06055393",
    sourceQuote: "Companies House PSC metadata."
  }
];


export const charges = chargeFacts.map((charge) => ({
  ...charge,
  charge_code: charge.chargeCode,
  created_date: charge.createdDate,
  source_id: charge.sourceId,
  source_quote: charge.sourceQuote
}));

export const officers = officerFacts.map((officer) => ({
  ...officer,
  source_id: officer.sourceId,
  source_quote: officer.sourceQuote
}));

export const ownership = {
  ...ownershipFacts[0],
  owner_name: ownershipFacts[0].ownerName,
  control_type: ownershipFacts[0].controlType,
  percentage_band: ownershipFacts[0].percentageBand,
  source_id: ownershipFacts[0].sourceId,
  source_quote: ownershipFacts[0].sourceQuote
};

export function loadManifest(): DataroomManifest {
  const raw = readFileSync(MANIFEST_PATH, "utf-8");
  const manifest = JSON.parse(raw) as DataroomManifest;
  return {
    ...manifest,
    sources: manifest.sources.map(normalizeSource)
  };
}


export const manifest = loadManifest();
export const sources = manifest.sources;
export const sourceCategories = Array.from(new Set(sources.map((source) => source.category))).sort();
export const indexedSourceCount = sources.filter((source) => source.indexed).length;

export function getSources(): ManifestSource[] {
  return loadManifest().sources;
}

export function sourceById(sourceId: string): ManifestSource | undefined {
  return getSources().find((source) => source.source_id === sourceId || source.sourceId === sourceId);
}

export function citation(sourceId: string, snippet?: string, page: number | null = null): Citation {
  const source = sourceById(sourceId);
  if (!source) throw new Error(`source_id is not in manifest: ${sourceId}`);
  const resolvedSnippet = snippet ?? snippetForSource(sourceId);
  return {
    source_id: source.source_id,
    sourceId: source.source_id,
    title: source.title,
    category: source.category,
    source_url: source.source_url,
    url: source.source_url,
    page,
    snippet: resolvedSnippet
  };
}


export function snippetForSource(sourceId: string, maxLength = 320): string | undefined {
  const source = sourceById(sourceId);
  if (!source) return undefined;
  const text = loadSourceText(source);
  return text ? toSnippet(text, maxLength) : undefined;
}

export function loadSourceChunks(): SourceChunk[] {
  return getSources().flatMap((source) => {
    const text = loadSourceText(source);
    return chunkText(text, source).map((textChunk, index) => ({
      chunkId: `${source.source_id}:${index + 1}`,
      sourceId: source.source_id,
      title: source.title,
      category: source.category,
      page: null,
      text: textChunk
    }));
  });
}

export function retrieveSourceChunks(question: string, limit = 5): SourceChunk[] {
  const queryTerms = tokenize(question);
  if (!queryTerms.length) return [];

  return loadSourceChunks()
    .map((chunk) => ({ ...chunk, score: scoreChunk(chunk, queryTerms) }))
    .filter((chunk) => (chunk.score ?? 0) > 0)
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0) || a.sourceId.localeCompare(b.sourceId))
    .slice(0, limit);
}

export function sourceExists(sourceId: string): boolean {
  return Boolean(sourceById(sourceId));
}

function normalizeSource(source: ManifestSource): ManifestSource {
  const processedPath = resolveProcessedPath(source);
  const processedText = processedPath && existsSync(processedPath) ? readFileSync(processedPath, "utf-8") : "";
  const indexed = Boolean(processedText);
  const sourceStatus = source.source_status ?? sourceStatusFor(source.processing_status, indexed);
  return {
    ...source,
    sourceId: source.source_id,
    workspaceId: WORKSPACE_ID,
    retrievedAt: source.retrieved_at,
    url: source.source_url,
    localPath: source.local_path,
    processedPath: source.processed_path,
    includedReason: source.included_reason,
    status: sourceStatus,
    source_status: sourceStatus,
    processing_status: source.processing_status,
    snippet: processedText ? toSnippet(processedText) : undefined,
    indexed
  };
}

function sourceStatusFor(processingStatus: string, indexed: boolean): string {
  if (processingStatus === "verified") return "verified";
  if (processingStatus === "processed" || indexed) return "processed";
  return "pending";
}


function resolveProcessedPath(source: ManifestSource): string | null {
  if (source.processed_path) return join(PROJECT_ROOT, source.processed_path);
  const processedName = processedPathBySourceId[source.source_id];
  return processedName ? join(PROCESSED_DIR, processedName) : null;
}

function toSnippet(text: string, maxLength = 320): string {
  const normalized = text
    .replace(/^#.+$/gm, "")
    .replace(/\s+/g, " ")
    .trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength - 1).trim()}...`;
}

function loadSourceText(source: ManifestSource): string {
  const processedPath = resolveProcessedPath(source);
  if (processedPath && existsSync(processedPath)) {
    return readFileSync(processedPath, "utf-8");
  }

  return [
    source.title,
    `Category: ${source.category}`,
    `Issuer: ${source.issuer}`,
    `Included reason: ${source.included_reason}`,
    source.notes ? `Notes: ${source.notes}` : ""
  ].filter(Boolean).join("\n");
}

function chunkText(text: string, source: ManifestSource): string[] {
  const normalized = text.replace(/\r\n/g, "\n").replace(/[ \t]+/g, " ").trim();
  if (!normalized) return [];
  const maxChars = 1200;
  const chunks: string[] = [];
  for (let start = 0; start < normalized.length; start += maxChars) {
    chunks.push(normalized.slice(start, start + maxChars));
  }
  return chunks.length ? chunks : [source.title];
}

function scoreChunk(chunk: SourceChunk, queryTerms: string[]): number {
  const textTerms = tokenize(`${chunk.title} ${chunk.category} ${chunk.text}`);
  const counts = new Map<string, number>();
  for (const term of textTerms) counts.set(term, (counts.get(term) ?? 0) + 1);
  return queryTerms.reduce((score, term) => score + (counts.get(term) ?? 0), 0);
}

function tokenize(value: string): string[] {
  return value.toLowerCase().match(/[a-z0-9][a-z0-9&'_-]*/g) ?? [];
}

function findProjectRoot(): string {
  let current = process.cwd();
  for (let i = 0; i < 8; i += 1) {
    if (existsSync(join(current, "dataroom", "manifest.json"))) return current;
    const parent = resolve(current, "..");
    if (parent === current) break;
    current = parent;
  }
  return dirname(dirname(dirname(new URL(import.meta.url).pathname)));
}
