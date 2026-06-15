type LabelDictionary = Record<string, string>;

const FIELD_LABELS: LabelDictionary = {
  source_count: "Documents",
  indexed_count: "Search-ready documents",
  indexed_source_count: "Search-ready documents",
  usedInAnswers: "Available for answers",
  used_in_answers: "Available for answers",
  reviewed: "Source checked",
  sourceId: "Source",
  source_id: "Source",
  workspaceId: "Workspace",
  workspace_id: "Workspace",
  periodEnd: "Period end",
  period_end: "Period end",
  reportedOrComputed: "Basis",
  reported_or_computed: "Basis",
  financial_facts: "Financial figures"
};

const CATEGORY_LABELS: LabelDictionary = {
  accounts: "Financial filings",
  financial_filings: "Financial filings",
  charges: "Charges & security",
  charges_register: "Charges & security",
  company_profile: "Company profile",
  filing_history: "Filing history",
  management: "Ownership & management",
  ownership: "Ownership & management",
  ownership_management: "Ownership & management",
  news: "News & events",
  news_events: "News & events",
  industry_context: "Market context"
};

const STATUS_LABELS: LabelDictionary = {
  downloaded: "Pending review",
  pending: "Pending review",
  pending_download: "Not searchable yet",
  pending_manual_curation: "Pending review",
  processed: "Ready",
  indexed: "Ready",
  verified: "Ready"
};

const BASIS_LABELS: LabelDictionary = {
  computed: "Computed from source figures",
  reported: "Reported in source",
  unavailable: "Not available in reviewed sources",
  unknown: "Unknown"
};

const CONFIDENCE_LABELS: LabelDictionary = {
  high: "High confidence",
  low: "Low confidence",
  medium: "Medium confidence"
};

const MISSING_INFORMATION_LABELS: LabelDictionary = {
  "reviewed usable financial_facts": "Financial figures are pending source review before use in answers.",
  revenue: "Reviewed revenue figures are not available yet.",
  turnover: "Reviewed turnover figures are not available yet.",
  EBITDA: "Reviewed EBITDA figures are not available yet.",
  ebitda: "Reviewed EBITDA figures are not available yet.",
  debt: "Reviewed debt figures are not available yet.",
  borrowings: "Reviewed borrowing figures are not available yet.",
  structured_covenant_terms: "Covenant information is not available in the public dataroom.",
  private_information_not_in_dataroom: "Private information is not available in this dataroom.",
  "supported financial metric": "No reviewed financial figures are available yet.",
  "retrieved manifest-backed evidence": "No matching reviewed source was found in the dataroom.",
  financial_facts: "No reviewed financial figures are available yet.",
  charges: "Reviewed charge details are not available yet.",
  "OpenAI Responses API completion": "The answer service is temporarily unavailable.",
  USE_OPENAI_SYNTHESIS: "Answer synthesis is not enabled for this workspace.",
  OPENAI_API_KEY: "Answer synthesis is not configured for this workspace."
};

export function displayLabel(key: unknown): string {
  if (key === null || key === undefined || key === "") return "";
  const value = String(key);
  return FIELD_LABELS[value] ?? humanizeKey(value);
}

export function displaySourceCategory(category: string | null | undefined): string {
  if (!category) return "Dataroom";
  const key = normalizeKey(category);
  return CATEGORY_LABELS[key] ?? humanizeKey(category);
}

export function displayStatus(status: string | null | undefined): string {
  if (!status) return "";
  const key = normalizeKey(status);
  return STATUS_LABELS[key] ?? humanizeKey(status);
}

export function displayBasis(value: string | null | undefined): string {
  if (!value) return "";
  const key = normalizeKey(value);
  return BASIS_LABELS[key] ?? humanizeKey(value);
}

export function displayConfidence(value: string | null | undefined): string {
  if (!value) return "";
  const key = normalizeKey(value);
  return CONFIDENCE_LABELS[key] ?? humanizeKey(value);
}

export function displayMissingInformation(item: string): string {
  const normalized = item.trim();
  const normalizedKey = normalized.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  if (MISSING_INFORMATION_LABELS[normalized] || MISSING_INFORMATION_LABELS[normalizedKey]) {
    return MISSING_INFORMATION_LABELS[normalized] ?? MISSING_INFORMATION_LABELS[normalizedKey];
  }

  return Object.entries({ ...FIELD_LABELS, ...BASIS_LABELS }).reduce(
    (label, [rawKey, polishedLabel]) => replaceRawToken(label, rawKey, polishedLabel.toLowerCase()),
    humanizeKey(normalized)
  );
}

export function displayCountLabel(key: "source_count" | "indexed_count" | "indexed_source_count", count: number): string {
  const label = displayLabel(key);
  return `${count} ${count === 1 ? singularize(label) : label.toLowerCase()}`;
}

function replaceRawToken(text: string, rawKey: string, replacement: string): string {
  return text.replace(new RegExp(escapeRegExp(rawKey), "g"), replacement);
}

function normalizeKey(key: string): string {
  return key.trim().toLowerCase().replace(/[\s-]+/g, "_");
}

function humanizeKey(key: string): string {
  const words = key
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .trim()
    .toLowerCase();

  return words ? words.charAt(0).toUpperCase() + words.slice(1) : key;
}

function singularize(label: string): string {
  return label.endsWith("s") ? label.slice(0, -1) : label;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function sourceReferenceKey(source: { source_id?: string; sourceId?: string; title?: string }, index: number): string {
  return `${source.source_id ?? source.sourceId ?? source.title ?? "source"}-${index}`;
}

export function categoryLabel(value: string | null | undefined): string {
  return displaySourceCategory(value);
}

export function statusLabel(value: string | null | undefined): string {
  return displayStatus(value) || "Pending review";
}

export function missingInformationLabel(value: string | null | undefined): string {
  return displayMissingInformation(value ?? "");
}

export function confidenceLabel(value: string | null | undefined): string {
  return displayConfidence(value);
}

export function formatRetrievedDate(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric" }).format(date);
}
