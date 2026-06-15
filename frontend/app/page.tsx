"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Landmark, PanelRightOpen } from "lucide-react";
import { ChatPanel } from "@/components/chat-panel";
import { SourceBrowser } from "@/components/source-browser";
import { getSources } from "@/lib/api";
import type { InspectionState, Source } from "@/lib/types";

export default function Home() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loadingSources, setLoadingSources] = useState(true);
  const [sourceError, setSourceError] = useState<string | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [inspection, setInspection] = useState<InspectionState>({
    citations: [],
    reviewedFacts: [],
    missingInformation: []
  });

  useEffect(() => {
    let active = true;

    getSources()
      .then((nextSources) => {
        if (!active) return;
        setSources(nextSources);
        setSourceError(null);
      })
      .catch((error) => {
        if (!active) return;
        setSourceError(
          error instanceof Error ? error.message : "Unable to load dataroom documents."
        );
      })
      .finally(() => {
        if (active) setLoadingSources(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const readyDocuments = useMemo(
    () => sources.filter((source) => ["processed", "verified", "indexed"].includes(source.source_status ?? source.status ?? source.processing_status ?? "")).length,
    [sources]
  );

  return (
    <main className="min-h-screen bg-platform text-ink">
      <div className="flex min-h-screen flex-col">
        <header className="sticky top-0 z-30 border-b border-line bg-white/95 px-4 py-3 backdrop-blur sm:px-6 xl:px-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gold text-ink">
                <Landmark size={20} aria-hidden="true" />
              </div>
              <div>
                <p className="text-sm font-semibold text-ink">Goldborne Capital</p>
                <p className="text-xs text-ink/58">Dataroom: GAIL&apos;S Limited</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <div className="hidden items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-sm text-emerald-900 sm:flex">
                <CheckCircle2 size={15} aria-hidden="true" />
                AI analyst online
              </div>
              <button
                className="inline-flex items-center gap-2 rounded-md border border-line bg-white px-3 py-2 text-sm font-medium text-ink shadow-sm hover:border-moss"
                type="button"
                onClick={() => setInspectorOpen((current) => !current)}
                aria-label={inspectorOpen ? "Collapse dataroom inspector" : "Open dataroom inspector"}
              >
                <PanelRightOpen size={17} aria-hidden="true" />
                {inspectorOpen ? "Hide dataroom" : "View dataroom"}
              </button>
            </div>
          </div>
        </header>

        <section className={`min-h-0 flex-1 transition-[padding] duration-200 ${inspectorOpen ? "lg:pr-[420px]" : ""}`}>
          <div className="flex min-h-[calc(100vh-65px)] flex-col bg-white">
            <div className="border-b border-line bg-paper/70 px-4 py-4 sm:px-7">
              <div className="mx-auto flex max-w-4xl flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase text-moss">AI dataroom analyst</p>
                  <h1 className="mt-2 text-2xl font-semibold tracking-normal text-ink sm:text-3xl">
                    Ask questions. Get cited answers.
                  </h1>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-ink/62">
                    A clean credit diligence workspace for GAIL&apos;S Limited, grounded in reviewed documents and structured facts.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2 text-sm text-ink/68">
                  <span className="rounded-full border border-line bg-white px-3 py-1.5">{sources.length || "No"} documents</span>
                  <span className="rounded-full border border-line bg-white px-3 py-1.5">{readyDocuments} ready for search</span>
                  <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1.5 text-amber-900">Financial figures awaiting source review</span>
                </div>
              </div>
            </div>
            <ChatPanel
              onInspectionUpdate={setInspection}
              onOpenInspector={() => setInspectorOpen(true)}
            />
          </div>
        </section>

        <SourceBrowser
          sources={sources}
          loading={loadingSources}
          error={sourceError}
          inspection={inspection}
          open={inspectorOpen}
          onClose={() => setInspectorOpen(false)}
        />
      </div>
    </main>
  );
}
