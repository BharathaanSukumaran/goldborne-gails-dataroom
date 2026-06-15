"use client";

import { useEffect, useMemo, useState } from "react";
import { Landmark, PanelRightClose, PanelRightOpen } from "lucide-react";
import { ChatPanel } from "@/components/chat-panel";
import { SourceBrowser } from "@/components/source-browser";
import { getSources } from "@/lib/api";
import type { InspectionState, Source } from "@/lib/types";

export default function Home() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loadingSources, setLoadingSources] = useState(true);
  const [sourceError, setSourceError] = useState<string | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);
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
    () =>
      sources.filter((source) =>
        ["processed", "verified", "indexed"].includes(
          source.source_status ?? source.status ?? source.processing_status ?? ""
        )
      ).length,
    [sources]
  );

  useEffect(() => {
    const wideViewport = window.matchMedia("(min-width: 1536px)");
    const frame = window.requestAnimationFrame(() => {
      setInspectorOpen(wideViewport.matches);
    });

    const handleViewportChange = (event: MediaQueryListEvent) => {
      setInspectorOpen(event.matches);
    };

    wideViewport.addEventListener("change", handleViewportChange);
    return () => {
      window.cancelAnimationFrame(frame);
      wideViewport.removeEventListener("change", handleViewportChange);
    };
  }, []);

  return (
    <main className="min-h-screen bg-platform text-ink">
      <div className="flex min-h-screen flex-col">
        <header className="sticky top-0 z-30 border-b border-line bg-white/95 px-4 py-2.5 backdrop-blur sm:px-6 xl:px-8">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gold text-ink">
                <Landmark size={18} aria-hidden="true" />
              </div>
              <div>
                <p className="text-sm font-semibold text-ink">Goldborne Capital</p>
                <p className="text-xs text-ink/58">AI dataroom analyst</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <div className="hidden text-sm text-ink/62 sm:block">Dataroom: GAIL&apos;S Limited</div>
              <button
                className="inline-flex items-center gap-2 rounded-md border border-line bg-white px-3 py-2 text-sm font-medium text-ink shadow-sm hover:border-moss"
                type="button"
                onClick={() => setInspectorOpen((current) => !current)}
                aria-label={inspectorOpen ? "Collapse dataroom inspector" : "Open dataroom inspector"}
                aria-expanded={inspectorOpen}
              >
                {inspectorOpen ? <PanelRightClose size={17} aria-hidden="true" /> : <PanelRightOpen size={17} aria-hidden="true" />}
                {inspectorOpen ? "Hide dataroom" : "View dataroom"}
              </button>
            </div>
          </div>
        </header>

        <section className={`min-h-0 flex-1 transition-[padding] duration-200 ${inspectorOpen ? "2xl:pr-[360px]" : ""}`}>
          <div className="flex min-h-[calc(100vh-58px)] flex-col bg-white">
            <div className="border-b border-line bg-paper/70 px-4 py-5 sm:px-7">
              <div className="mx-auto max-w-4xl">
                <h1 className="text-2xl font-semibold tracking-normal text-ink sm:text-3xl">
                  Ask anything about the GAIL&apos;S Limited dataroom.
                </h1>
                <p className="mt-2 text-sm leading-6 text-ink/62">
                  Answers are grounded in reviewed documents and cited sources.
                </p>
                <p className="mt-3 text-xs text-ink/46">
                  {sources.length || "No"} documents · {readyDocuments} ready · Financial figures pending review.
                </p>
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
