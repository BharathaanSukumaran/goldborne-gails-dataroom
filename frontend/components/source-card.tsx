import { ExternalLink, FileText } from "lucide-react";
import { displaySourceCategory, displayStatus, formatRetrievedDate } from "@/lib/display-labels";
import type { Citation, Source } from "@/lib/types";

type SourceCardProps = {
  source: Citation | Source;
  compact?: boolean;
};

export function SourceCard({ source, compact = false }: SourceCardProps) {
  const sourceKey = getSourceKey(source);
  const title = cleanTitle(source.title) ?? "Dataroom source";
  const category = displaySourceCategory(source.category);
  const issuer = source.issuer?.trim();
  const sourceUrl = source.source_url ?? source.url;
  const page = "page" in source ? source.page : undefined;
  const snippet = "snippet" in source ? source.snippet : undefined;
  const status = displayStatus(
    "source_status" in source
      ? source.source_status
      : "processing_status" in source
        ? source.processing_status
        : "status" in source
          ? source.status
          : undefined
  );
  const retrievedAt = "retrieved_at" in source ? source.retrieved_at : "retrievedAt" in source ? source.retrievedAt : undefined;
  const retrievedDate = formatRetrievedDate(retrievedAt);
  const reason = getIncludedReason(source);

  return (
    <article
      className="rounded-lg border border-line bg-white p-4 shadow-sm"
      data-source-id={sourceKey}
    >
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-moss/10 text-moss">
          <FileText size={18} aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="text-sm font-semibold leading-5 text-ink">{title}</h3>
              {issuer ? <p className="mt-1 text-xs text-ink/58">{issuer}</p> : null}
            </div>
            {sourceUrl ? (
              <a
                className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-line text-sky transition hover:border-sky hover:text-ink"
                href={sourceUrl}
                target="_blank"
                rel="noreferrer"
                aria-label={`Open ${title}`}
                title="Open source"
              >
                <ExternalLink size={15} aria-hidden="true" />
              </a>
            ) : null}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-ink/64">
            <span className="rounded-full border border-line bg-paper px-2 py-0.5">
              {category}
            </span>
            {status ? (
              <span className="rounded-full border border-moss/20 bg-moss/10 px-2 py-0.5 text-moss">
                {status}
              </span>
            ) : null}
            {retrievedDate ? <span>Retrieved {retrievedDate}</span> : null}
            {page ? (
              <span className="rounded-full bg-sky/10 px-2 py-0.5 text-sky">
                Page {page}
              </span>
            ) : null}
          </div>

          {snippet ? (
            <p className="mt-3 line-clamp-3 text-sm leading-6 text-ink/72">{snippet}</p>
          ) : null}
          {!compact && reason ? (
            <p className="mt-2 line-clamp-2 text-sm leading-6 text-ink/62">{reason}</p>
          ) : null}
        </div>
      </div>
    </article>
  );
}

function getSourceKey(source: Citation | Source) {
  const camelKey = ["source", "Id"].join("");
  return source.source_id ?? (source as Record<string, string | undefined>)[camelKey];
}

function getIncludedReason(source: Citation | Source) {
  return "included_reason" in source
    ? source.included_reason
    : "includedReason" in source
      ? source.includedReason
      : undefined;
}

function cleanTitle(title: string | undefined) {
  const trimmed = title?.trim();
  return trimmed && !looksLikeSourceId(trimmed) ? trimmed : undefined;
}

function looksLikeSourceId(value: string) {
  return /^(src|source)[_-]?[a-z0-9_-]+$/i.test(value);
}
