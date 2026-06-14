"use client";

import { useEffect, useState } from "react";
import { ChatPanel } from "@/components/chat-panel";
import { SourceBrowser } from "@/components/source-browser";
import { getSources } from "@/lib/api";
import type { Source } from "@/lib/types";

export default function Home() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loadingSources, setLoadingSources] = useState(true);
  const [sourceError, setSourceError] = useState<string | null>(null);

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
          error instanceof Error ? error.message : "Unable to load dataroom sources."
        );
      })
      .finally(() => {
        if (active) setLoadingSources(false);
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="flex min-h-screen flex-col lg:h-screen lg:flex-row lg:overflow-hidden">
      <ChatPanel />
      <div className="lg:w-[390px] xl:w-[440px]">
        <SourceBrowser sources={sources} loading={loadingSources} error={sourceError} />
      </div>
    </main>
  );
}
