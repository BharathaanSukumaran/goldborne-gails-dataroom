import type { Config, Context } from "@netlify/functions";
import { charges, citation, officers, ownership } from "./_shared/data";

const unknown = (missing: string[], answer = "I cannot answer that from the current dataroom evidence.") =>
  Response.json({ answer, answer_type: "unknown", facts_used: [], citations: [], missing_information: missing, confidence: "low" });

function answerQuestion(question: string) {
  const q = question.toLowerCase();
  if (["covenant", "private", "banking headroom"].some((term) => q.includes(term))) {
    return { answer: "I cannot answer that from the current dataroom evidence.", answer_type: "unknown", facts_used: [], citations: [], missing_information: ["structured covenant/private information not in dataroom"], confidence: "low" };
  }
  if (["revenue", "ebitda", "debt", "borrowings"].some((term) => q.includes(term))) {
    return { answer: "For the latest seeded reporting period, revenue, EBITDA unknown status, and debt cannot be stated from reviewed structured facts yet. The source accounts PDFs must be ingested and reviewed first.", answer_type: "unknown", facts_used: [], citations: [], missing_information: ["revenue", "EBITDA", "debt"], confidence: "low" };
  }
  if (["risk", "summary", "credit"].some((term) => q.includes(term))) {
    const citations = [citation("ch-charge-0006", charges[0].source_quote), citation("ch-charge-0005", charges[1].source_quote), citation("ch-psc-06055393", "Companies House PSC metadata."), citation("news-expansion-2025-placeholder", "Curated expansion news placeholder."), citation("news-community-context-2024-placeholder", "Curated community reaction news placeholder.")];
    const answer = q.includes("summary") || q.includes("credit")
      ? "Business overview: Gail's is represented as a UK bakery/cafe operator in the dataroom. Ownership: Bread Limited is recorded as active PSC with 75% or more control. Financial snapshot: revenue, EBITDA unknown status, and debt remain open until reviewed accounts are ingested. Security/charges: the dataroom records two outstanding Glas Trust Corporation Limited charges. Key risks: expansion execution, lease/capex exposure, local-community reaction, and information gaps on reviewed lender metrics. Open questions: reviewed accounts PDFs and any covenant package are required before final credit metrics can be stated."
      : "Key lender risks visible in the current dataroom are security/lender exposure from two outstanding Glas Trust Corporation Limited charges, expansion execution and lease/capex exposure from the curated expansion source, local-community reaction from the curated community source, and information risk because revenue, EBITDA unknown status, debt and covenants need reviewed source documents before final lender metrics can be stated.";
    return { answer, answer_type: "hybrid", facts_used: charges, citations, missing_information: [], confidence: "medium" };
  }
  if (["charge", "charges", "security", "lender"].some((term) => q.includes(term))) {
    return { answer: charges.map((charge) => `Charge ${charge.charge_code} was created on ${charge.created_date}; status ${charge.status}; holder/person entitled: ${charge.holder}.`).join(" "), answer_type: "structured", facts_used: charges, citations: charges.map((charge) => citation(charge.source_id, charge.source_quote)), missing_information: [], confidence: "high" };
  }
  if (["director", "directors", "management", "officer"].some((term) => q.includes(term))) {
    return { answer: "Current directors/officers in the dataroom: " + officers.map((officer) => `${officer.name} (${officer.role})`).join("; ") + ".", answer_type: "structured", facts_used: officers, citations: [citation("ch-officers-06055393", "Companies House officers metadata.")], missing_information: [], confidence: "high" };
  }
  if (["owner", "ownership", "psc", "ultimate"].some((term) => q.includes(term))) {
    return { answer: `${ownership.owner_name} is an ${ownership.status} ${ownership.control_type} with ${ownership.percentage_band} control.`, answer_type: "structured", facts_used: [ownership], citations: [citation("ch-psc-06055393", "Companies House PSC metadata.")], missing_information: [], confidence: "high" };
  }
  return { answer: "I cannot answer that from the current dataroom evidence.", answer_type: "unknown", facts_used: [], citations: [], missing_information: ["No matching structured fact or retrieved evidence"], confidence: "low" };
}

export default async (req: Request, _context: Context) => {
  if (req.method !== "POST") return Response.json({ detail: "Method not allowed" }, { status: 405 });
  const body = await req.json().catch(() => ({}));
  if (!body.question || typeof body.question !== "string") return unknown(["question"]);
  return Response.json(answerQuestion(body.question));
};

export const config: Config = { path: "/api/ask" };
