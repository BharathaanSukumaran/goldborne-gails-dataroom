import { ExternalLink, FileText } from "lucide-react";
import { displaySourceCategory } from "@/lib/display-labels";
import type { Citation, Source } from "@/lib/types";

type SourceCardProps = {
  source: Citation | Source;
  compact?: boolean;
};

export function SourceCard({ source }: SourceCardProps) {
  const title = cleanTitle(source) ?? "Dataroom source";
  const category = displaySourceCategory(source.category);
  const sourceUrl = source.source_url ?? source.url;
  const page = "page" in source ? source.page : undefined;
  const snippet = "snippet" in source ? source.snippet : undefined;
  const hasPage = page !== undefined && page !== null && page !== "";

  return (
    <article className="rounded-lg border border-line bg-white p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-moss/10 text-moss">
          <FileText size={18} aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="text-sm font-semibold leading-5 text-ink">{title}</h3>
            </div>
            {sourceUrl ? (
              <a
                className="inline-flex h-8 shrink-0 items-center gap-1 rounded-md border border-line px-2 text-xs font-medium text-sky transition hover:border-sky hover:text-ink"
                href={sourceUrl}
                target="_blank"
                rel="noreferrer"
                aria-label={`Open ${title}`}
                title="Open source"
              >
                <ExternalLink size={14} aria-hidden="true" />
                <span>Open source</span>
              </a>
            ) : null}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-ink/64">
            <span className="rounded-full border border-line bg-paper px-2 py-0.5">
              {category}
            </span>
            {hasPage ? (
              <span className="rounded-full bg-sky/10 px-2 py-0.5 text-sky">
                Page {page}
              </span>
            ) : null}
          </div>

          {snippet ? (
            <p className="mt-3 line-clamp-3 text-sm leading-6 text-ink/72">{snippet}</p>
          ) : null}
        </div>
      </div>
    </article>
  );
}

function cleanTitle(source: Citation | Source) {
  const trimmed = source.title?.trim();
  if (!trimmed) return undefined;
  if (trimmed === source.source_id || trimmed === source.sourceId) return undefined;
  return looksLikeSourceId(trimmed) ? undefined : trimmed;
}

function looksLikeSourceId(value: string) {
  return /^(src|source)[_-]?[a-z0-9_-]+$/i.test(value) || /^[a-z]{2,}(?:-[a-z0-9]+)+-\d{3,}$/i.test(value);
}
