export type Citation = {
  source_id?: string;
  sourceId?: string;
  title?: string;
  category?: string;
  source_url?: string;
  page?: number | string | null;
  snippet?: string;
  url?: string;
};

export type AskResponse = {
  answer: string;
  answerType?: string;
  answer_type?: string;
  factsUsed?: unknown[];
  facts_used?: unknown[];
  citations?: Citation[];
  missingInformation?: string[];
  missing_information?: string[];
  confidence?: "low" | "medium" | "high" | string;
};

export type Source = {
  source_id: string;
  sourceId?: string;
  workspaceId?: string;
  title: string;
  category: string;
  issuer?: string;
  retrieved_at?: string;
  retrievedAt?: string;
  source_url?: string;
  url?: string;
  local_path?: string;
  localPath?: string;
  included_reason?: string;
  includedReason?: string;
  processing_status?: string;
  source_status?: string;
  status?: string;
};

export type AskRequest = {
  workspaceId: "gails-limited";
  question: string;
};
