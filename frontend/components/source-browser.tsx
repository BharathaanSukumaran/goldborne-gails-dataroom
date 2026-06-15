"use client";

import { AlertCircle, CheckCircle2, Database, FileText, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import {
  categoryLabel,
  confidenceLabel,
  displayBasis,
  displayLabel,
  missingInformationLabel,
  sourceReferenceKey,
  statusLabel
} from "@/lib/display-labels";
import type { Citation, InspectionState, ReviewedFact, Source } from "@/lib/types";
import { SourceCard } from "./source-card";

type SourceBrowserProps = {
  sources: Source[];
  loading: boolean;
  error: string | null;
  inspection: InspectionState;
  open: boolean;
  onClose: () => void;
};

type TabId = "documents" | "database" | "reviewed" | "missing";

const tabs: Array<{ id: TabId; label: string }> = [
  { id: "documents", label: "Documents" },
  { id: "database", label: "Database" },
  { id: "reviewed", label: "Reviewed facts" },
  { id: "missing", label: "Missing information" }
];

const databaseGroups = [
  {
    label: "Company details",
    categories: ["Company profile", "Filing history"],
    description: "Companies House identity and filings."
  },
  {
    label: "Financial facts",
    categories: ["Financial filings"],
    description: "Filed accounts pending source review."
  },
  {
    label: "Charges & security",
    categories: ["Charges & security"],
    description: "Registered security records."
  },
  {
    label: "Ownership & management",
    categories: ["Ownership & management"],
    description: "Directors, officers, and control records."
  },
  {
    label: "News & events",
    categories: ["News & events", "Market context"],
    description: "Curated public context."
  }
];

export function SourceBrowser({ sources, loading, error, inspection, open, onClose }: SourceBrowserProps) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");
  const [activeTab, setActiveTab] = useState<TabId>("documents");

  const categories = useMemo(
    () => [
      { label: "All", value: "All" },
      ...Array.from(new Set(sources.map((source) => source.category)))
        .sort((left, right) => categoryLabel(left).localeCompare(categoryLabel(right)))
        .map((value) => ({ label: categoryLabel(value), value }))
    ],
    [sources]
  );

  const readyCount = useMemo(
    () =>
      sources.filter((source) =>
        ["processed", "verified", "indexed"].includes(
          source.source_status ?? source.status ?? source.processing_status ?? ""
        )
      ).length,
    [sources]
  );
  const pendingCount = Math.max(sources.length - readyCount, 0);

  const filteredSources = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return sources.filter((source) => {
      const matchesCategory = category === "All" || source.category === category;
      const text = `${source.title} ${categoryLabel(source.category)} ${source.issuer ?? ""} ${source.included_reason ?? ""}`.toLowerCase();
      return matchesCategory && (!normalizedQuery || text.includes(normalizedQuery));
    });
  }, [category, query, sources]);

  const content = (
    <aside className="flex h-full min-h-0 flex-col bg-white/95">
      <div className="border-b border-line p-3 sm:p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase text-moss">Dataroom</p>
            <h2 className="mt-1 text-sm font-semibold text-ink">Sources</h2>
            <p className="mt-1 text-xs text-ink/58">
              {sources.length || "No"} documents · {readyCount} ready · {pendingCount} pending
            </p>
          </div>
          <button
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-line bg-white text-ink/64 hover:text-ink"
            type="button"
            onClick={onClose}
            aria-label="Close dataroom inspector"
            title="Close inspector"
          >
            <X size={17} aria-hidden="true" />
          </button>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-1 rounded-md border border-line bg-paper p-1 text-xs">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={`min-h-8 rounded px-2 py-1.5 text-center transition ${
                activeTab === tab.id ? "bg-moss text-white" : "text-ink/64 hover:bg-white hover:text-ink"
              }`}
              type="button"
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3 sm:p-4">
        {activeTab === "documents" ? (
          <DocumentsTab
            categories={categories}
            category={category}
            error={error}
            filteredSources={filteredSources}
            loading={loading}
            query={query}
            setCategory={setCategory}
            setQuery={setQuery}
          />
        ) : null}
        {activeTab === "database" ? <DatabaseTab sources={sources} /> : null}
        {activeTab === "reviewed" ? <ReviewedFactsTab inspection={inspection} /> : null}
        {activeTab === "missing" ? <MissingInformationTab inspection={inspection} /> : null}
      </div>
    </aside>
  );

  return (
    <>
      <div
        className={`fixed inset-y-0 right-0 z-20 hidden w-[360px] border-l border-line bg-white shadow-panel transition-transform duration-200 2xl:block ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {content}
      </div>
      {open ? (
        <div className="fixed inset-0 z-40 2xl:hidden" role="dialog" aria-modal="true" aria-label="Dataroom inspector">
          <button className="absolute inset-0 bg-ink/35" type="button" onClick={onClose} aria-label="Close dataroom inspector" />
          <div className="absolute inset-y-0 right-0 w-full max-w-sm border-l border-line bg-white shadow-2xl">
            {content}
          </div>
        </div>
      ) : null}
    </>
  );
}

function DocumentsTab({
  categories,
  category,
  error,
  filteredSources,
  loading,
  query,
  setCategory,
  setQuery
}: {
  categories: Array<{ label: string; value: string }>;
  category: string;
  error: string | null;
  filteredSources: Source[];
  loading: boolean;
  query: string;
  setCategory: (category: string) => void;
  setQuery: (query: string) => void;
}) {
  return (
    <div>
      <label className="flex items-center gap-2 rounded-md border border-line bg-white px-3 py-2">
        <Search size={17} className="text-ink/46" aria-hidden="true" />
        <input
          className="w-full bg-transparent text-sm outline-none placeholder:text-ink/38"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search documents"
          aria-label="Search documents"
        />
      </label>
      <div className="mt-3 flex gap-1.5 overflow-x-auto pb-1">
        {categories.map((item) => (
          <button
            key={item.value}
            className={`shrink-0 rounded-md border px-2.5 py-1 text-xs transition ${
              category === item.value
                ? "border-moss bg-moss text-white"
                : "border-line bg-white text-ink/72 hover:border-ink/30"
            }`}
            onClick={() => setCategory(item.value)}
            type="button"
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="mt-2 space-y-1.5">
        {loading ? (
          <SourceSkeleton />
        ) : error ? (
          <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            {error}
          </div>
        ) : filteredSources.length ? (
          filteredSources.map((source) => <SourceCard key={source.source_id} source={source} compact />)
        ) : (
          <div className="rounded-md border border-dashed border-line bg-white/70 p-4 text-sm text-ink/62">
            No documents match your current search.
          </div>
        )}
      </div>
    </div>
  );
}

function DatabaseTab({ sources }: { sources: Source[] }) {
  return (
    <div className="space-y-2">
      {databaseGroups.map((group) => {
        const groupSources = sources.filter((source) => group.categories.includes(categoryLabel(source.category)));
        const ready = groupSources.filter((source) =>
          ["processed", "verified", "indexed"].includes(
            source.source_status ?? source.status ?? source.processing_status ?? ""
          )
        ).length;

        return (
          <article key={group.label} className="rounded-md border border-line bg-white p-3">
            <div className="flex items-start gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-moss/10 text-moss">
                <Database size={17} aria-hidden="true" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-semibold text-ink">{group.label}</h3>
                  <span className="shrink-0 rounded-full border border-line bg-paper px-2 py-0.5 text-xs text-ink/62">
                    {ready}/{groupSources.length}
                  </span>
                </div>
                <p className="mt-1 text-xs leading-5 text-ink/58">{group.description}</p>
                <div className="mt-2 space-y-1.5">
                  {groupSources.slice(0, 3).map((source) => (
                    <div key={source.source_id} className="flex items-start gap-2 text-xs text-ink/58">
                      <FileText size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
                      <span className="min-w-0 flex-1 truncate">{source.title}</span>
                      <span>{statusLabel(source.source_status ?? source.status ?? source.processing_status)}</span>
                    </div>
                  ))}
                  {groupSources.length > 3 ? (
                    <p className="text-xs text-ink/42">+{groupSources.length - 3} more linked documents</p>
                  ) : null}
                  {!groupSources.length ? (
                    <p className="text-xs text-ink/48">No linked documents.</p>
                  ) : null}
                </div>
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}

function ReviewedFactsTab({ inspection }: { inspection: InspectionState }) {
  const facts = inspection.reviewedFacts;
  const citations = inspection.citations;
  const citationTitlesById = useMemo(() => sourceTitlesById(citations), [citations]);

  if (!facts.length && !citations.length) {
    return (
      <EmptyState
        title="No reviewed facts have been used yet"
        description="Ask a question to see the evidence behind an answer."
      />
    );
  }

  return (
    <div className="space-y-3">
      {inspection.confidence ? (
        <div className="rounded-md border border-line bg-white p-3 text-sm text-ink/68">
          <span className="font-medium text-ink">Answer confidence:</span> {confidenceLabel(inspection.confidence)}
        </div>
      ) : null}
      {facts.length ? (
        <div className="space-y-2">
          {facts.map((fact, index) => (
            <FactCard key={index} fact={fact} index={index} sourceTitlesById={citationTitlesById} />
          ))}
        </div>
      ) : (
        <EmptyState
          title="No reviewed financial figures are available yet"
          description="The latest answer returned citations but no reviewed facts."
        />
      )}
      {citations.length ? (
        <section aria-label="Latest citations">
          <p className="mb-2 text-xs font-semibold uppercase text-ink/50">Latest citations</p>
          <div className="space-y-2">
            {citations.map((citation, index) => (
              <SourceCard key={sourceReferenceKey(citation, index)} source={citation} compact />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function MissingInformationTab({ inspection }: { inspection: InspectionState }) {
  const missing = inspection.missingInformation;

  if (!missing.length) {
    return (
      <div className="flex gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
        <CheckCircle2 size={17} className="mt-0.5 shrink-0" aria-hidden="true" />
        <span>No missing information reported.</span>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {missing.map((item) => (
        <div key={item} className="flex gap-3 rounded-md border border-line bg-white p-3 text-sm text-ink/72">
          <AlertCircle size={17} className="mt-0.5 shrink-0 text-amber-700" aria-hidden="true" />
          <span>{missingInformationLabel(item)}</span>
        </div>
      ))}
    </div>
  );
}

function FactCard({
  fact,
  index,
  sourceTitlesById
}: {
  fact: ReviewedFact;
  index: number;
  sourceTitlesById: Map<string, string>;
}) {
  const display = factDisplay(fact, index, sourceTitlesById);
  const rows = [
    { label: "Fact", value: display.fact },
    { label: "Value", value: display.value },
    { label: "Period", value: display.period },
    { label: "Source", value: display.source },
    { label: "Status", value: display.status }
  ];

  return (
    <article className="rounded-md border border-line bg-white p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink">{display.fact}</p>
          {display.value ? <p className="mt-1 break-words text-sm font-semibold text-moss">{display.value}</p> : null}
        </div>
        <span className="shrink-0 rounded-full border border-line bg-paper px-2 py-0.5 text-xs text-ink/60">
          Reviewed
        </span>
      </div>
      <dl className="mt-3 grid gap-2 text-xs">
        {rows.map((row) => (
          <div key={row.label} className="grid grid-cols-[76px_minmax(0,1fr)] gap-3 border-t border-line/70 pt-2">
            <dt className="text-xs font-medium uppercase text-ink/45">{row.label}</dt>
            <dd className="min-w-0 break-words text-ink/70">{row.value ?? "Not specified"}</dd>
          </div>
        ))}
      </dl>
    </article>
  );
}

function factDisplay(fact: ReviewedFact, index: number, sourceTitlesById: Map<string, string>) {
  const factName = findFirstEntry(fact, [
    "metric",
    "charge_id",
    "charge_code",
    "name",
    "owner_name",
    "control_type",
    "role",
    "title",
    "category",
    "label",
    "fact",
    "field",
    "type"
  ]);
  const sourceId = findFirstValue(fact, ["source_document_id", "sourceDocumentId", "source_id", "sourceId"]);

  return {
    fact: formatFactName(factName, index),
    value: formatFactValue(fact),
    period: findFirstValue(fact, ["period", "periodEnd", "period_end", "year", "created_date", "created_on", "date"]),
    source: cleanSourceValue(
      findFirstValue(fact, ["source_title", "sourceTitle", "source_name", "sourceName", "source"]),
      sourceId,
      sourceTitlesById
    ),
    status: formatFactStatus(fact)
  };
}

function sourceTitlesById(citations: Citation[]) {
  const titlesById = new Map<string, string>();

  citations.forEach((citation) => {
    const citationRecord = citation as unknown as Record<string, unknown>;
    const title = cleanDisplayValue(citation.title);
    const ids = [
      citation.source_id,
      citation.sourceId,
      readScalar(citationRecord, "source_document_id"),
      readScalar(citationRecord, "sourceDocumentId")
    ];

    ids.forEach((id) => {
      if (id && title && !looksLikeInternalId(title)) titlesById.set(id, title);
    });
  });

  return titlesById;
}

function formatFactName(entry: { key: string; value: string } | null, index: number) {
  if (!entry) return "Reviewed fact " + (index + 1);
  if (["charge_id", "charge_code"].includes(entry.key)) return "Charge " + entry.value;
  if (["name", "owner_name", "title"].includes(entry.key)) return cleanDisplayValue(entry.value) ?? "Reviewed fact " + (index + 1);
  return displayLabel(entry.value);
}

function formatFactValue(fact: ReviewedFact) {
  const entry = findFirstEntry(fact, [
    "value",
    "amount",
    "reported_value",
    "reportedValue",
    "persons_entitled",
    "holder",
    "percentage_band",
    "status",
    "snippet",
    "source_quote",
    "sourceQuote"
  ]);

  if (!entry) return null;

  const currency = findFirstValue(fact, ["currency"]);
  const metric = findFirstValue(fact, ["metric"]);
  if (currency && isNumericString(entry.value) && metric && ["revenue", "turnover", "ebitda", "debt", "borrowings"].includes(metric.toLowerCase())) {
    return formatMinorUnitMoney(entry.value, currency);
  }

  const value = entry.key === "status" ? displayLabel(entry.value) : entry.value;
  const unit = findFirstValue(fact, ["unit"]);
  return unit && !["minor_units", "none"].includes(unit.toLowerCase()) ? value + " " + unit : value;
}

function formatFactStatus(fact: ReviewedFact) {
  const reviewed = readBoolean(fact, "reviewed");
  if (reviewed !== null) return reviewed ? "Reviewed" : "Pending review";

  const usedInAnswers = readBoolean(fact, "used_in_answers") ?? readBoolean(fact, "usedInAnswers");
  if (usedInAnswers !== null) return usedInAnswers ? "Available for answers" : "Held for review";

  const status = findFirstValue(fact, ["status", "source_status", "processing_status"]);
  if (status) return statusLabel(status);

  const basis = findFirstValue(fact, ["reportedOrComputed", "reported_or_computed", "basis"]);
  return displayBasis(basis) || "Reviewed";
}

function findFirstEntry(record: ReviewedFact, keys: string[]) {
  for (const key of keys) {
    const value = readScalar(record, key);
    if (value) return { key, value };
  }
  return null;
}

function findFirstValue(record: ReviewedFact, keys: string[]) {
  for (const key of keys) {
    const value = readScalar(record, key);
    if (value) return value;
  }
  return null;
}

function readScalar(record: Record<string, unknown>, key: string) {
  return formatScalar(record[key]);
}

function formatScalar(value: unknown): string | null {
  if (typeof value === "string") return cleanDisplayValue(value);
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  if (Array.isArray(value)) {
    const items = value.map(formatScalar).filter((item): item is string => Boolean(item));
    return items.length ? items.join(", ") : null;
  }
  return null;
}

function readBoolean(record: ReviewedFact, key: string) {
  const value = record[key];
  if (typeof value === "boolean") return value;
  if (typeof value === "string" && ["true", "false"].includes(value.toLowerCase())) return value.toLowerCase() === "true";
  return null;
}

function cleanDisplayValue(value: string | null | undefined) {
  const trimmed = value?.trim();
  return trimmed || null;
}

function cleanSourceValue(value: string | null, sourceId: string | null, sourceTitlesById: Map<string, string>) {
  const resolvedTitle = sourceId ? sourceTitlesById.get(sourceId) : null;
  if (resolvedTitle) return resolvedTitle;
  if (!value || looksLikeInternalId(value)) return sourceId ? "Referenced source" : null;
  return value;
}

function looksLikeInternalId(value: string) {
  return /^(src|source|ch|ft|guardian|news)[_-][a-z0-9_-]+$/i.test(value) || /^[a-z]{2,}(?:-[a-z0-9]+)+-\d{3,}$/i.test(value);
}

function isNumericString(value: string) {
  return /^-?\d+(?:\.\d+)?$/.test(value);
}

function formatMinorUnitMoney(value: string, currency: string) {
  const amount = Number(value) / 100;
  if (!Number.isFinite(amount)) return displayLabel(value);

  try {
    return new Intl.NumberFormat("en-GB", {
      style: "currency",
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(amount);
  } catch {
    return currency + " " + amount.toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
}

function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-md border border-dashed border-line bg-white/70 p-4 text-sm text-ink/62">
      <p className="font-medium text-ink">{title}</p>
      <p className="mt-1 leading-5">{description}</p>
    </div>
  );
}

function SourceSkeleton() {
  return (
    <>
      {[0, 1, 2].map((item) => (
        <div key={item} className="rounded-md border border-line bg-white p-3">
          <div className="h-4 w-3/4 animate-pulse rounded bg-line" />
          <div className="mt-3 h-3 w-full animate-pulse rounded bg-line/70" />
          <div className="mt-2 h-3 w-2/3 animate-pulse rounded bg-line/70" />
        </div>
      ))}
    </>
  );
}
