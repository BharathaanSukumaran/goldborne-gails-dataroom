export type Citation = {
  source_id?: string;
  title?: string;
  category?: string;
  page?: number | string | null;
  snippet?: string;
  url?: string;
};

export type AskResponse = {
  answer: string;
  answer_type?: string;
  citations?: Citation[];
  missing_information?: string[];
  confidence?: "low" | "medium" | "high" | string;
};

export type Source = {
  source_id: string;
  title: string;
  category: string;
  issuer?: string;
  retrieved_at?: string;
  source_url?: string;
  local_path?: string;
  included_reason?: string;
  processing_status?: string;
};

export type AskRequest = {
  question: string;
};
