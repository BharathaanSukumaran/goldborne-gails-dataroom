"use client";

import { useEffect, useState } from "react";
import {
  BarChart3,
  Bot,
  BriefcaseBusiness,
  Building2,
  ChevronDown,
  Database,
  FileCheck2,
  Gauge,
  KeyRound,
  Landmark,
  Newspaper,
  ShieldCheck,
  UsersRound
} from "lucide-react";
import { ChatPanel } from "@/components/chat-panel";
import { SourceBrowser } from "@/components/source-browser";
import { getSources } from "@/lib/api";
import type { Source } from "@/lib/types";

const navigation = [
  { label: "Dashboard", icon: Gauge },
  { label: "Workspaces", icon: BriefcaseBusiness },
  { label: "Dataroom", icon: Database },
  { label: "Financials", icon: BarChart3 },
  { label: "Charges & Security", icon: ShieldCheck },
  { label: "Ownership & Management", icon: UsersRound },
  { label: "News & Events", icon: Newspaper },
  { label: "AI Analyst", icon: Bot },
  { label: "Sources", icon: FileCheck2 }
];

const intelligenceCards = [
  {
    title: "Company Overview",
    icon: Building2,
    eyebrow: "Selected workspace",
    value: "GAIL'S Limited",
    detail: "UK bakery and cafe operator diligence case study with evidence-backed company intelligence."
  },
  {
    title: "Financial Snapshot",
    icon: BarChart3,
    eyebrow: "Review focus",
    value: "Revenue, EBITDA, leverage",
    detail: "Ask the analyst to extract reported period metrics, profitability movement, and lender-relevant ratios."
  },
  {
    title: "Dataroom Coverage",
    icon: Database,
    eyebrow: "Indexed sources",
    value: "Live source register",
    detail: "Search filings, news, financial documents, and supporting materials loaded through the source API."
  },
  {
    title: "Charges & Security",
    icon: KeyRound,
    eyebrow: "Security review",
    value: "Registered charges",
    detail: "Surface secured parties, charge status, and collateral context from available filings."
  },
  {
    title: "Ownership & Management",
    icon: UsersRound,
    eyebrow: "Control analysis",
    value: "Directors and owners",
    detail: "Review management signals, ownership context, and governance facts grounded in sources."
  },
  {
    title: "AI Analyst Chat",
    icon: Bot,
    eyebrow: "Evidence first",
    value: "Cited diligence answers",
    detail: "Use the analyst to interrogate financials, risks, events, and gaps without changing the backend contract."
  }
];

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
    <main className="min-h-screen bg-platform text-ink">
      <div className="flex min-h-screen">
        <aside className="hidden w-72 shrink-0 border-r border-line bg-ink text-white lg:flex lg:flex-col">
          <div className="border-b border-white/10 px-6 py-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gold text-ink">
                <Landmark size={20} aria-hidden="true" />
              </div>
              <div>
                <p className="text-sm font-semibold">Goldborne Capital</p>
                <p className="text-xs text-white/60">Intelligence Platform</p>
              </div>
            </div>
          </div>
          <nav className="flex-1 space-y-1 px-3 py-4" aria-label="Platform navigation">
            {navigation.map((item, index) => {
              const Icon = item.icon;
              const active = index === 0;

              return (
                <a
                  key={item.label}
                  className={`flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition ${
                    active
                      ? "bg-white text-ink shadow-sm"
                      : "text-white/70 hover:bg-white/10 hover:text-white"
                  }`}
                  href="#dashboard"
                >
                  <Icon size={17} aria-hidden="true" />
                  {item.label}
                </a>
              );
            })}
          </nav>
          <div className="border-t border-white/10 p-4">
            <div className="rounded-lg border border-white/10 bg-white/5 p-3">
              <p className="text-xs uppercase text-white/50">Selected workspace</p>
              <p className="mt-1 text-sm font-semibold">GAIL&apos;S Limited</p>
              <p className="mt-1 text-xs leading-5 text-white/60">Case study workspace</p>
            </div>
          </div>
        </aside>

        <section className="min-w-0 flex-1">
          <header className="sticky top-0 z-10 border-b border-line bg-platform/95 px-4 py-4 backdrop-blur sm:px-6 xl:px-8">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase text-moss">Goldborne Capital</p>
                <h1 className="mt-1 text-2xl font-semibold text-ink sm:text-3xl">
                  Capital Intelligence Platform
                </h1>
              </div>
              <button
                className="flex w-full items-center justify-between rounded-lg border border-line bg-white px-4 py-3 text-left shadow-sm xl:w-[320px]"
                type="button"
              >
                <span>
                  <span className="block text-xs uppercase text-ink/50">Selected workspace</span>
                  <span className="mt-0.5 block text-sm font-semibold text-ink">GAIL&apos;S Limited</span>
                </span>
                <ChevronDown size={18} className="text-ink/50" aria-hidden="true" />
              </button>
            </div>
          </header>

          <div id="dashboard" className="space-y-6 px-4 py-5 sm:px-6 xl:px-8">
            <section className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3" aria-label="Dashboard cards">
              {intelligenceCards.map((card) => {
                const Icon = card.icon;

                return (
                  <article key={card.title} className="rounded-lg border border-line bg-white p-5 shadow-sm">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="text-xs font-semibold uppercase text-ink/50">{card.eyebrow}</p>
                        <h2 className="mt-2 text-base font-semibold text-ink">{card.title}</h2>
                      </div>
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-moss/10 text-moss">
                        <Icon size={19} aria-hidden="true" />
                      </div>
                    </div>
                    <p className="mt-4 text-xl font-semibold text-ink">{card.value}</p>
                    <p className="mt-2 text-sm leading-6 text-ink/60">{card.detail}</p>
                  </article>
                );
              })}
            </section>

            <section className="grid min-h-[720px] gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
              <div className="min-h-[680px] overflow-hidden rounded-lg border border-line bg-white shadow-sm">
                <ChatPanel />
              </div>
              <div className="min-h-[680px] overflow-hidden rounded-lg border border-line bg-paper shadow-sm">
                <SourceBrowser sources={sources} loading={loadingSources} error={sourceError} />
              </div>
            </section>
          </div>
        </section>
      </div>
    </main>
  );
}
