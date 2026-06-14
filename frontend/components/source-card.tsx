import { ExternalLink, FileText } from "lucide-react";
import type { Citation, Source } from "@/lib/types";

type SourceCardProps = {
  source: Citation | Source;
  compact?: boolean;
};

export function SourceCard({ source, compact = false }: SourceCardProps) {
  const title = source.title ?? ("source_id" in source ? source.source_id : "Source");
  const category = source.category ?? "Dataroom";
  const sourceUrl =
    "source_url" in source
      ? source.source_url
      : "url" in source
        ? source.url
        : undefined;
  const page = "page" in source ? source.page : undefined;
  const snippet = "snippet" in source ? source.snippet : undefined;
  const status =
    "source_status" in source
      ? source.source_status
      : "processing_status" in source
        ? source.processing_status
        : undefined;
  const reason = "included_reason" in source ? source.included_reason : undefined;

  return (
    <article className="rounded-lg border border-line bg-white/82 p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-moss/10 text-moss">
          <FileText size={18} aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-sm font-semibold text-ink">{title}</h3>
            <span className="rounded-full border border-line bg-paper px-2 py-0.5 text-xs text-ink/70">
              {category}
            </span>
            {page ? (
              <span className="rounded-full bg-sky/10 px-2 py-0.5 text-xs text-sky">
                p. {page}
              </span>
            ) : null}
          </div>
          {snippet ? (
            <p className="mt-2 line-clamp-3 text-sm leading-6 text-ink/72">{snippet}</p>
          ) : null}
          {!compact && reason ? (
            <p className="mt-2 line-clamp-2 text-sm leading-6 text-ink/62">{reason}</p>
          ) : null}
          <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-ink/56">
            {"source_id" in source ? <span>{source.source_id}</span> : null}
            {status ? <span>{status}</span> : null}
            {sourceUrl ? (
              <a
                className="inline-flex items-center gap-1 font-medium text-sky hover:text-ink"
                href={sourceUrl}
                target="_blank"
                rel="noreferrer"
              >
                Open source
                <ExternalLink size={13} aria-hidden="true" />
              </a>
            ) : null}
          </div>
        </div>
      </div>
    </article>
  );
}
