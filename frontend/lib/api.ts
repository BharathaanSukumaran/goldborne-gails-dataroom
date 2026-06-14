import type { AskRequest, AskResponse, Source } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers
    },
    cache: "no-store"
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function askDataroom(payload: Pick<AskRequest, "question">): Promise<AskResponse> {
  return requestJson<AskResponse>("/ask", {
    method: "POST",
    body: JSON.stringify({ workspaceId: "gails-limited", ...payload })
  });
}

export async function getSources(): Promise<Source[]> {
  const payload = await requestJson<unknown>("/sources");

  if (Array.isArray(payload)) {
    return payload.filter(isSource);
  }

  if (isRecord(payload) && Array.isArray(payload.sources)) {
    return payload.sources.filter(isSource);
  }

  if (isRecord(payload) && Array.isArray(payload.documents)) {
    return payload.documents.filter(isSource);
  }

  return [];
}

function isSource(value: unknown): value is Source {
  return (
    isRecord(value) &&
    typeof value.source_id === "string" &&
    typeof value.title === "string" &&
    typeof value.category === "string"
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
