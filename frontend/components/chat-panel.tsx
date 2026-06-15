"use client";

import { AlertCircle, Bot, Loader2, Send, UserRound } from "lucide-react";
import { FormEvent, useMemo, useRef, useState } from "react";
import { askDataroom } from "@/lib/api";
import { confidenceLabel, missingInformationLabel } from "@/lib/display-labels";
import type { AskResponse, Citation, InspectionState, ReviewedFact } from "@/lib/types";
import { SourceCard } from "./source-card";

const suggestedQuestions = [
  "Summarise this company for a credit committee.",
  "What charges are registered against the company?",
  "Who owns and manages the company?",
  "What financial information is available?",
  "What information is missing from the dataroom?"
];

type Message = {
  id: string;
  role: "assistant" | "user";
  content: string;
  citations?: Citation[];
  missingInformation?: string[];
  confidence?: string;
};

const initialMessage: Message = {
  id: "welcome",
  role: "assistant",
  content:
    "Ask anything about the GAIL'S Limited dataroom. I will answer from reviewed documents and show the sources I used. Financial figures are only used after source review."
};

type ChatPanelProps = {
  onInspectionUpdate?: (inspection: InspectionState) => void;
  onOpenInspector?: () => void;
};

export function ChatPanel({ onInspectionUpdate, onOpenInspector }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([initialMessage]);
  const [question, setQuestion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const canSubmit = useMemo(() => question.trim().length > 0 && !loading, [loading, question]);

  async function submitQuestion(nextQuestion = question) {
    const trimmedQuestion = nextQuestion.trim();
    if (!trimmedQuestion || loading) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmedQuestion
    };

    setMessages((current) => [...current, userMessage]);
    setQuestion("");
    setError(null);
    setLoading(true);

    try {
      const response: AskResponse = await askDataroom({ question: trimmedQuestion });
      const citations: Citation[] = response.citations ?? [];
      const missingInformation = response.missing_information ?? response.missingInformation ?? [];
      const reviewedFacts: ReviewedFact[] = response.facts_used ?? response.factsUsed ?? [];

      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: response.answer,
          citations,
          missingInformation,
          confidence: response.confidence
        }
      ]);
      onInspectionUpdate?.({
        citations,
        reviewedFacts,
        missingInformation,
        confidence: response.confidence
      });
      if (citations.length || missingInformation.length || reviewedFacts.length) {
        onOpenInspector?.();
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The dataroom analyst could not return an answer."
      );
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitQuestion();
  }

  return (
    <section className="flex h-full min-h-0 flex-1 flex-col bg-white">
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-7">
        <div className="mx-auto flex max-w-4xl flex-col gap-5">
          {messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))}

          {loading ? (
            <div className="flex items-center gap-3 rounded-lg border border-line bg-paper p-4 text-sm text-ink/64">
              <Loader2 size={18} className="animate-spin text-moss" aria-hidden="true" />
              Checking reviewed facts and dataroom evidence...
            </div>
          ) : null}

          {error ? (
            <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
              <AlertCircle size={18} className="mt-0.5 shrink-0" aria-hidden="true" />
              <div>
                <p className="font-medium">Unable to answer</p>
                <p className="mt-1 leading-6">{error}</p>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <div className="border-t border-line bg-paper/80 px-4 py-4 sm:px-7">
        <div className="mx-auto max-w-4xl">
          <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
            {suggestedQuestions.map((item) => (
              <button
                key={item}
                className="shrink-0 rounded-md border border-line bg-white px-3 py-2 text-left text-sm text-ink/72 transition hover:border-moss hover:text-ink"
                disabled={loading}
                onClick={() => void submitQuestion(item)}
                type="button"
              >
                {item}
              </button>
            ))}
          </div>
          <form className="flex items-end gap-3" onSubmit={onSubmit}>
            <textarea
              ref={textareaRef}
              className="max-h-44 min-h-16 flex-1 resize-y rounded-lg border border-line bg-white px-4 py-3 text-base leading-6 text-ink outline-none placeholder:text-ink/38"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void submitQuestion();
                }
              }}
              placeholder="Ask anything about this dataroom..."
              aria-label="Ask anything about this dataroom"
            />
            <button
              className="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg bg-moss text-white transition hover:bg-ink disabled:cursor-not-allowed disabled:bg-ink/28"
              disabled={!canSubmit}
              type="submit"
              aria-label="Send question"
              title="Send question"
            >
              {loading ? <Loader2 size={20} className="animate-spin" /> : <Send size={20} />}
            </button>
          </form>
        </div>
      </div>
    </section>
  );
}

function ChatMessage({ message }: { message: Message }) {
  const isAssistant = message.role === "assistant";

  return (
    <article className={`flex gap-3 ${isAssistant ? "" : "justify-end"}`}>
      {isAssistant ? (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-moss/10 text-moss">
          <Bot size={18} aria-hidden="true" />
        </div>
      ) : null}
      <div className={`max-w-[min(760px,100%)] ${isAssistant ? "w-full" : ""}`}>
        <div
          className={`rounded-lg border px-4 py-3 text-sm leading-6 ${
            isAssistant
              ? "border-line bg-paper text-ink"
              : "border-sky bg-sky text-white"
          }`}
        >
          {isAssistant ? <p className="mb-2 text-xs font-semibold uppercase text-moss">Direct answer</p> : null}
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>
        {message.missingInformation?.length ? (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <p className="font-medium">Missing information</p>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {message.missingInformation.map((item) => (
                <li key={item}>{missingInformationLabel(item)}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {message.citations?.length ? (
          <div className="mt-3">
            <p className="mb-2 text-xs font-semibold uppercase text-ink/48">Sources used</p>
            <div className="grid gap-3 md:grid-cols-2">
              {message.citations.map((citation, index) => (
                <SourceCard key={`${citation.title ?? "citation"}-${index}`} source={citation} compact />
              ))}
            </div>
          </div>
        ) : null}
        {message.confidence ? (
          <p className="mt-2 text-xs text-ink/48">{confidenceLabel(message.confidence)}</p>
        ) : null}
      </div>
      {!isAssistant ? (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-sky/10 text-sky">
          <UserRound size={18} aria-hidden="true" />
        </div>
      ) : null}
    </article>
  );
}
