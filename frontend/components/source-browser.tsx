"use client";

import { Search } from "lucide-react";
import { useMemo, useState } from "react";
import type { Source } from "@/lib/types";
import { SourceCard } from "./source-card";

type SourceBrowserProps = {
  sources: Source[];
  loading: boolean;
  error: string | null;
};

export function SourceBrowser({ sources, loading, error }: SourceBrowserProps) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");

  const categories = useMemo(
    () => ["All", ...Array.from(new Set(sources.map((source) => source.category))).sort()],
    [sources]
  );

  const statusSummary = useMemo(() => {
    const pending = sources.filter((source) => (source.source_status ?? source.status) === "pending").length;
    const processed = sources.filter((source) => (source.source_status ?? source.status) === "processed").length;
    return `${sources.length} sources: ${processed} processed, ${pending} pending`;
  }, [sources]);

  const filteredSources = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return sources.filter((source) => {
      const matchesCategory = category === "All" || source.category === category;
      const text = `${source.title} ${source.category} ${source.included_reason ?? ""}`.toLowerCase();
      return matchesCategory && (!normalizedQuery || text.includes(normalizedQuery));
    });
  }, [category, query, sources]);

  return (
    <aside className="flex h-full min-h-0 flex-col bg-paper/80">
      <div className="border-b border-line p-5">
        <div>
          <p className="text-xs font-semibold uppercase text-moss">Sources</p>
          <h2 className="mt-1 text-base font-semibold text-ink">Dataroom evidence</h2>
          <p className="mt-1 text-sm text-ink/62">{statusSummary} for GAIL&apos;S Limited</p>
        </div>
        <label className="mt-4 flex items-center gap-2 rounded-lg border border-line bg-white px-3 py-2">
          <Search size={17} className="text-ink/46" aria-hidden="true" />
          <input
            className="w-full bg-transparent text-sm outline-none placeholder:text-ink/38"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search sources"
            aria-label="Search sources"
          />
        </label>
        <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
          {categories.map((item) => (
            <button
              key={item}
              className={`shrink-0 rounded-md border px-3 py-1.5 text-sm transition ${
                category === item
                  ? "border-moss bg-moss text-white"
                  : "border-line bg-white text-ink/72 hover:border-ink/30"
              }`}
              onClick={() => setCategory(item)}
              type="button"
            >
              {item}
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-5">
        {loading ? (
          <SourceSkeleton />
        ) : error ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            {error}
          </div>
        ) : filteredSources.length ? (
          filteredSources.map((source) => (
            <SourceCard key={source.source_id} source={source} compact />
          ))
        ) : (
          <div className="rounded-lg border border-dashed border-line bg-white/70 p-5 text-sm text-ink/62">
            No sources match the current filters.
          </div>
        )}
      </div>
    </aside>
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
