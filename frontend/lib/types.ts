export type Citation = {
  source_id?: string;
  sourceId?: string;
  title?: string;
  category?: string;
  issuer?: string;
  source_url?: string;
  page?: number | string | null;
  snippet?: string;
  url?: string;
  included_reason?: string;
  includedReason?: string;
  processing_status?: string;
  source_status?: string;
  status?: string;
};

export type AskResponse = {
  answer: string;
  answerType?: string;
  answer_type?: string;
  factsUsed?: ReviewedFact[];
  facts_used?: ReviewedFact[];
  citations?: Citation[];
  missingInformation?: string[];
  missing_information?: string[];
  confidence?: "low" | "medium" | "high" | string;
};

export type ReviewedFact = Record<string, unknown>;

export type InspectionState = {
  citations: Citation[];
  reviewedFacts: ReviewedFact[];
  missingInformation: string[];
  confidence?: string;
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
