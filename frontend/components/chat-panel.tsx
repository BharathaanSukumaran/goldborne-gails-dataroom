"use client";

import { AlertCircle, Bot, Loader2, Send, UserRound } from "lucide-react";
import { FormEvent, useMemo, useRef, useState } from "react";
import { askDataroom } from "@/lib/api";
import type { AskResponse, Citation } from "@/lib/types";
import { SourceCard } from "./source-card";

const suggestedQuestions = [
  "What was revenue and EBITDA in the last reported year?",
  "What charges are registered against the company and who holds them?",
  "Summarize ownership and management signals.",
  "Draft a lender-focused credit summary."
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
    "Ask about the selected GAIL'S Limited workspace: financials, charges, ownership, management, news, or lender risks. Answers are grounded in dataroom sources where the backend has evidence."
};

export function ChatPanel() {
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
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: response.answer,
          citations: response.citations ?? [],
          missingInformation: response.missing_information ?? [],
          confidence: response.confidence
        }
      ]);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The dataroom API did not return a usable response."
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
      <header className="border-b border-line px-5 py-4 sm:px-7">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase text-moss">AI Analyst</p>
            <h2 className="mt-1 text-xl font-semibold text-ink">Evidence-backed diligence chat</h2>
          </div>
          <div className="rounded-md border border-line bg-paper px-3 py-2 text-sm text-ink/68">
            Workspace: GAIL&apos;S Limited
          </div>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-7">
        <div className="mx-auto flex max-w-4xl flex-col gap-5">
          {messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))}

          {loading ? (
            <div className="flex items-center gap-3 rounded-lg border border-line bg-paper p-4 text-sm text-ink/64">
              <Loader2 size={18} className="animate-spin text-moss" aria-hidden="true" />
              Checking structured facts and dataroom evidence...
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

      <div className="border-t border-line bg-paper/80 px-5 py-4 sm:px-7">
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
              className="max-h-36 min-h-12 flex-1 resize-y rounded-lg border border-line bg-white px-4 py-3 text-sm leading-6 text-ink outline-none placeholder:text-ink/38"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void submitQuestion();
                }
              }}
              placeholder="Ask the AI analyst about this workspace"
              aria-label="Question"
            />
            <button
              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-moss text-white transition hover:bg-ink disabled:cursor-not-allowed disabled:bg-ink/28"
              disabled={!canSubmit}
              type="submit"
              aria-label="Send question"
              title="Send question"
            >
              {loading ? <Loader2 size={19} className="animate-spin" /> : <Send size={19} />}
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
      <div className={`max-w-[min(720px,100%)] ${isAssistant ? "w-full" : ""}`}>
        <div
          className={`rounded-lg border px-4 py-3 text-sm leading-6 ${
            isAssistant
              ? "border-line bg-paper text-ink"
              : "border-sky bg-sky text-white"
          }`}
        >
          {message.content}
        </div>
        {message.missingInformation?.length ? (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <p className="font-medium">Missing information</p>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {message.missingInformation.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {message.citations?.length ? (
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {message.citations.map((citation, index) => (
              <SourceCard
                key={`${citation.source_id ?? citation.title ?? "citation"}-${index}`}
                source={citation}
                compact
              />
            ))}
          </div>
        ) : null}
        {message.confidence ? (
          <p className="mt-2 text-xs text-ink/48">Confidence: {message.confidence}</p>
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
