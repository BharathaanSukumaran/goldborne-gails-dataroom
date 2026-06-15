"use client";

import { AlertCircle, CheckCircle2, Database, FileText, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import {
  categoryLabel,
  confidenceLabel,
  displayLabel,
  missingInformationLabel,
  sourceReferenceKey,
  statusLabel
} from "@/lib/display-labels";
import type { InspectionState, ReviewedFact, Source } from "@/lib/types";
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
    description: "Company identity and filing context from Companies House."
  },
  {
    label: "Financial facts",
    categories: ["Financial filings"],
    description: "Filed accounts are awaiting source review before figures can be used in answers."
  },
  {
    label: "Charges & security",
    categories: ["Charges & security"],
    description: "Registered security and charge-holder records."
  },
  {
    label: "Ownership & management",
    categories: ["Ownership & management"],
    description: "Directors, officers, and ownership/control records."
  },
  {
    label: "News & events",
    categories: ["News & events", "Market context"],
    description: "Curated public context for business and risk analysis."
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
    <aside className="flex h-full min-h-0 flex-col bg-paper/95">
      <div className="border-b border-line p-4 sm:p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase text-moss">Dataroom</p>
            <h2 className="mt-1 text-base font-semibold text-ink">GAIL&apos;S Limited evidence</h2>
            <p className="mt-1 text-sm text-ink/62">
              {sources.length || "No"} documents, {readyCount} ready for search, {pendingCount} pending review
            </p>
          </div>
          <button
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-line bg-white text-ink/64 hover:text-ink"
            type="button"
            onClick={onClose}
            aria-label="Close dataroom inspector"
            title="Close inspector"
          >
            <X size={17} aria-hidden="true" />
          </button>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2 rounded-lg border border-line bg-white p-1 text-sm sm:grid-cols-4 lg:grid-cols-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={`min-h-10 rounded-md px-2 py-2 text-center transition ${
                activeTab === tab.id ? "bg-moss text-white" : "text-ink/68 hover:bg-paper hover:text-ink"
              }`}
              type="button"
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-5">
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
        className={`fixed inset-y-0 right-0 z-20 hidden w-[420px] border-l border-line bg-paper shadow-panel transition-transform duration-200 lg:block ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {content}
      </div>
      {open ? (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Dataroom inspector">
          <button className="absolute inset-0 bg-ink/35" type="button" onClick={onClose} aria-label="Close dataroom inspector" />
          <div className="absolute inset-y-0 right-0 w-full max-w-md border-l border-line bg-paper shadow-2xl">
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
      <label className="flex items-center gap-2 rounded-lg border border-line bg-white px-3 py-2">
        <Search size={17} className="text-ink/46" aria-hidden="true" />
        <input
          className="w-full bg-transparent text-sm outline-none placeholder:text-ink/38"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search documents"
          aria-label="Search documents"
        />
      </label>
      <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
        {categories.map((item) => (
          <button
            key={item.value}
            className={`shrink-0 rounded-md border px-3 py-1.5 text-sm transition ${
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

      <div className="mt-4 space-y-3">
        {loading ? (
          <SourceSkeleton />
        ) : error ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            {error}
          </div>
        ) : filteredSources.length ? (
          filteredSources.map((source) => <SourceCard key={source.source_id} source={source} compact />)
        ) : (
          <div className="rounded-lg border border-dashed border-line bg-white/70 p-5 text-sm text-ink/62">
            No documents match your current search.
          </div>
        )}
      </div>
    </div>
  );
}

function DatabaseTab({ sources }: { sources: Source[] }) {
  return (
    <div className="space-y-3">
      {databaseGroups.map((group) => {
        const groupSources = sources.filter((source) => group.categories.includes(categoryLabel(source.category)));
        const ready = groupSources.filter((source) =>
          ["processed", "verified", "indexed"].includes(
            source.source_status ?? source.status ?? source.processing_status ?? ""
          )
        ).length;

        return (
          <article key={group.label} className="rounded-lg border border-line bg-white p-4">
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-moss/10 text-moss">
                <Database size={17} aria-hidden="true" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-semibold text-ink">{group.label}</h3>
                  <span className="shrink-0 rounded-full border border-line bg-paper px-2 py-0.5 text-xs text-ink/62">
                    {ready}/{groupSources.length}
                  </span>
                </div>
                <p className="mt-1 text-sm leading-6 text-ink/62">{group.description}</p>
                <div className="mt-3 space-y-2">
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
                    <p className="text-xs text-ink/48">No linked documents available yet.</p>
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

  if (!facts.length && !citations.length) {
    return (
      <EmptyState
        title="No reviewed facts selected"
        description="Ask the analyst a question to see the facts and cited evidence used in the latest answer."
      />
    );
  }

  return (
    <div className="space-y-4">
      {inspection.confidence ? (
        <div className="rounded-lg border border-line bg-white p-4 text-sm text-ink/68">
          <span className="font-medium text-ink">Answer confidence:</span> {confidenceLabel(inspection.confidence)}
        </div>
      ) : null}
      {facts.length ? (
        <div className="space-y-3">
          {facts.map((fact, index) => (
            <FactCard key={index} fact={fact} index={index} />
          ))}
        </div>
      ) : (
        <EmptyState
          title="No structured facts returned"
          description="The latest answer used citations but did not return structured reviewed facts."
        />
      )}
      {citations.length ? (
        <section aria-label="Latest cited documents">
          <p className="mb-2 text-xs font-semibold uppercase text-ink/50">Latest cited documents</p>
          <div className="space-y-3">
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
        <span>The latest answer did not report missing information.</span>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {missing.map((item) => (
        <div key={item} className="flex gap-3 rounded-lg border border-line bg-white p-4 text-sm text-ink/72">
          <AlertCircle size={17} className="mt-0.5 shrink-0 text-amber-700" aria-hidden="true" />
          <span>{missingInformationLabel(item)}</span>
        </div>
      ))}
    </div>
  );
}

function FactCard({ fact, index }: { fact: ReviewedFact; index: number }) {
  const entries = Object.entries(fact).filter(([, value]) => value !== null && value !== undefined && value !== "");
  const title = findFirstValue(fact, ["metric", "name", "label", "fact", "field", "type"]) ?? `Reviewed fact ${index + 1}`;
  const value = findFirstValue(fact, ["value", "amount", "reported_value", "reportedValue"]);

  return (
    <article className="rounded-lg border border-line bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink">{displayLabel(title)}</p>
          {value ? <p className="mt-1 text-base font-semibold text-moss">{displayLabel(value)}</p> : null}
        </div>
        <span className="shrink-0 rounded-full border border-line bg-paper px-2 py-0.5 text-xs text-ink/60">
          Reviewed
        </span>
      </div>
      <dl className="mt-3 grid gap-2 text-sm">
        {entries.slice(0, 8).map(([key, value]) => (
          <div key={key} className="grid grid-cols-[120px_minmax(0,1fr)] gap-3 border-t border-line/70 pt-2">
            <dt className="text-xs font-medium uppercase text-ink/45">{displayLabel(key)}</dt>
            <dd className="min-w-0 break-words text-ink/70">{displayLabel(value)}</dd>
          </div>
        ))}
      </dl>
    </article>
  );
}

function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-lg border border-dashed border-line bg-white/70 p-5 text-sm text-ink/62">
      <p className="font-medium text-ink">{title}</p>
      <p className="mt-1 leading-6">{description}</p>
    </div>
  );
}

function SourceSkeleton() {
  return (
    <>
      {[0, 1, 2].map((item) => (
        <div key={item} className="rounded-lg border border-line bg-white p-4">
          <div className="h-4 w-3/4 animate-pulse rounded bg-line" />
          <div className="mt-3 h-3 w-full animate-pulse rounded bg-line/70" />
          <div className="mt-2 h-3 w-2/3 animate-pulse rounded bg-line/70" />
        </div>
      ))}
    </>
  );
}

function findFirstValue(record: ReviewedFact, keys: string[]) {
  for (const key of keys) {
    const value = record[key];
    if (value !== null && value !== undefined && value !== "") return String(value);
  }
  return null;
}
