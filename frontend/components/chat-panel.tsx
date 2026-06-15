"use client";

import { AlertCircle, Bot, Loader2, Pencil, Send, UserRound } from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { askDataroom } from "@/lib/api";
import { confidenceLabel, displayChargeFieldIntent, displayLabel, missingInformationLabel } from "@/lib/display-labels";
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
  fieldIntent?: string;
  resolvedChargeCode?: string;
};

const initialMessage: Message = {
  id: "welcome",
  role: "assistant",
  content:
    "Ask questions about the GAIL'S Limited dataroom. I will answer from reviewed documents and show the sources I used."
};

type ChatPanelProps = {
  onInspectionUpdate?: (inspection: InspectionState) => void;
  onOpenInspector?: () => void;
};

export function ChatPanel({ onInspectionUpdate, onOpenInspector }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([initialMessage]);
  const [question, setQuestion] = useState("");
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  const canSubmit = useMemo(() => question.trim().length > 0 && !loading, [loading, question]);
  const showSuggestions = messages.length === 1 && !editingMessageId;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading, error]);

  useEffect(() => {
    resizeComposer();
  }, [question]);

  async function submitQuestion(nextQuestion = question) {
    const trimmedQuestion = nextQuestion.trim();
    if (!trimmedQuestion || loading) return;

    const editedId = editingMessageId;
    const userMessage: Message = {
      id: editedId ?? crypto.randomUUID(),
      role: "user",
      content: trimmedQuestion
    };

    setQuestion("");
    setEditingMessageId(null);
    setError(null);
    setLoading(true);

    setMessages((current) => {
      if (!editedId) return [...current, userMessage];

      const editIndex = current.findIndex((message) => message.id === editedId);
      if (editIndex === -1) return [...current, userMessage];

      return [...current.slice(0, editIndex), userMessage];
    });

    try {
      const response: AskResponse = await askDataroom({ question: trimmedQuestion });
      const citations: Citation[] = response.citations ?? [];
      const missingInformation = response.missing_information ?? response.missingInformation ?? [];
      const reviewedFacts: ReviewedFact[] = response.facts_used ?? response.factsUsed ?? [];
      const fieldIntent = response.field_intent ?? response.fieldIntent;
      const resolvedChargeCode = response.resolved_charge_code ?? response.resolvedChargeCode;

      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: response.answer,
          citations,
          missingInformation,
          confidence: response.confidence,
          fieldIntent,
          resolvedChargeCode
        }
      ]);
      onInspectionUpdate?.({
        citations,
        reviewedFacts,
        missingInformation,
        confidence: response.confidence,
        fieldIntent,
        resolvedChargeCode
      });
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

  function startEditing(message: Message) {
    if (loading) return;
    setEditingMessageId(message.id);
    setQuestion(message.content);
    setError(null);
    requestAnimationFrame(() => textareaRef.current?.focus());
  }

  function cancelEditing() {
    setEditingMessageId(null);
    setQuestion("");
    textareaRef.current?.focus();
  }

  function resizeComposer() {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 176)}px`;
  }

  return (
    <section className="relative flex h-full min-h-0 flex-1 flex-col bg-white">
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-5 pb-8 sm:px-7">
        <div className="mx-auto flex max-w-4xl flex-col gap-5">
          {messages.map((message) => (
            <ChatMessage
              key={message.id}
              message={message}
              loading={loading}
              onEdit={startEditing}
              onOpenInspector={onOpenInspector}
            />
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
          <div ref={endRef} />
        </div>
      </div>

      <div className="sticky bottom-0 z-10 border-t border-line bg-white/95 px-4 py-4 shadow-[0_-16px_36px_rgba(21,23,18,0.08)] backdrop-blur sm:px-7">
        <div className="mx-auto max-w-4xl">
          {showSuggestions ? (
            <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
              {suggestedQuestions.map((item) => (
                <button
                  key={item}
                  className="shrink-0 rounded-md border border-line bg-white px-3 py-2 text-left text-sm text-ink/72 transition hover:border-moss hover:text-ink"
                  disabled={loading}
                  onClick={() => {
                    void submitQuestion(item);
                  }}
                  type="button"
                >
                  {item}
                </button>
              ))}
            </div>
          ) : null}
          {editingMessageId ? (
            <div className="mb-2 flex items-center justify-between gap-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              <span>Editing your previous question. Sending will replace the following thread.</span>
              <button className="font-medium hover:text-ink" type="button" onClick={cancelEditing}>
                Cancel
              </button>
            </div>
          ) : null}
          <form className="rounded-xl border border-line bg-white p-2 shadow-sm focus-within:border-moss" onSubmit={onSubmit}>
            <div className="flex items-end gap-2">
              <textarea
                ref={textareaRef}
                className="max-h-44 min-h-12 flex-1 resize-none bg-transparent px-3 py-3 text-base leading-6 text-ink outline-none placeholder:text-ink/38"
                value={question}
                rows={1}
                onChange={(event) => setQuestion(event.target.value)}
                onInput={resizeComposer}
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
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-moss text-white transition hover:bg-ink disabled:cursor-not-allowed disabled:bg-ink/28"
                disabled={!canSubmit}
                type="submit"
                aria-label={editingMessageId ? "Update question" : "Send question"}
                title={editingMessageId ? "Update question" : "Send question"}
              >
                {loading ? <Loader2 size={19} className="animate-spin" /> : <Send size={19} />}
              </button>
            </div>
          </form>
        </div>
      </div>
    </section>
  );
}

function ChatMessage({
  message,
  loading,
  onEdit,
  onOpenInspector
}: {
  message: Message;
  loading: boolean;
  onEdit: (message: Message) => void;
  onOpenInspector?: () => void;
}) {
  const isAssistant = message.role === "assistant";

  return (
    <article className={`group flex gap-3 ${isAssistant ? "" : "justify-end"}`}>
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
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>
        {!isAssistant ? (
          <div className="mt-2 flex justify-end">
            <button
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-ink/48 opacity-100 transition hover:bg-paper hover:text-ink sm:opacity-0 sm:group-hover:opacity-100"
              type="button"
              disabled={loading}
              onClick={() => onEdit(message)}
            >
              <Pencil size={13} aria-hidden="true" />
              Edit
            </button>
          </div>
        ) : null}
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
        {isAssistant && (message.fieldIntent || message.resolvedChargeCode) ? (
          <dl className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink/56">
            {message.fieldIntent ? (
              <div className="flex gap-1">
                <dt>{displayLabel("fieldIntent")}:</dt>
                <dd className="font-medium text-ink/70">{displayChargeFieldIntent(message.fieldIntent)}</dd>
              </div>
            ) : null}
            {message.resolvedChargeCode ? (
              <div className="flex gap-1">
                <dt>{displayLabel("resolvedChargeCode")}:</dt>
                <dd className="font-medium text-ink/70">{message.resolvedChargeCode}</dd>
              </div>
            ) : null}
          </dl>
        ) : null}
        {message.citations?.length ? (
          <div className="mt-3">
            <div className="mb-2 flex items-center justify-between gap-3">
              <p className="text-xs font-semibold uppercase text-ink/48">Sources used</p>
              {onOpenInspector ? (
                <button
                  className="rounded-md px-2 py-1 text-xs font-medium text-sky hover:bg-paper hover:text-ink"
                  type="button"
                  onClick={onOpenInspector}
                >
                  View in dataroom
                </button>
              ) : null}
            </div>
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
