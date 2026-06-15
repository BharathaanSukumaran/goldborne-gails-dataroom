#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-https://goldborne-gails-dataroom.netlify.app}"
BASE_URL="${BASE_URL%/}"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

page_html="$tmp_dir/page.html"
health_json="$tmp_dir/health.json"
sources_json="$tmp_dir/sources.json"
ask_credit_json="$tmp_dir/ask_credit.json"
ask_financial_json="$tmp_dir/ask_financial.json"
ask_unsupported_json="$tmp_dir/ask_unsupported.json"

curl -fsSL "$BASE_URL/" -o "$page_html"
curl -fsSL "$BASE_URL/api/health" -o "$health_json"
curl -fsSL "$BASE_URL/api/sources" -o "$sources_json"

curl -fsSL "$BASE_URL/api/ask" \
  -H "Content-Type: application/json" \
  -d '{"workspaceId":"gails-limited","question":"Summarise the business and credit context for GAILS Limited using the dataroom."}' \
  -o "$ask_credit_json"

curl -fsSL "$BASE_URL/api/ask" \
  -H "Content-Type: application/json" \
  -d '{"workspaceId":"gails-limited","question":"What are revenue, EBITDA and debt for the latest year?"}' \
  -o "$ask_financial_json"

curl -fsSL "$BASE_URL/api/ask" \
  -H "Content-Type: application/json" \
  -d '{"workspaceId":"gails-limited","question":"What are the covenant headroom, facility margin and private banking terms?"}' \
  -o "$ask_unsupported_json"

node - "$page_html" "$health_json" "$sources_json" "$ask_credit_json" "$ask_financial_json" "$ask_unsupported_json" <<'NODE'
const fs = require("node:fs");
const [pagePath, healthPath, sourcesPath, askCreditPath, askFinancialPath, askUnsupportedPath] = process.argv.slice(2);
const page = fs.readFileSync(pagePath, "utf8");
const health = JSON.parse(fs.readFileSync(healthPath, "utf8"));
const sourcesPayload = JSON.parse(fs.readFileSync(sourcesPath, "utf8"));
const askCredit = JSON.parse(fs.readFileSync(askCreditPath, "utf8"));
const askFinancial = JSON.parse(fs.readFileSync(askFinancialPath, "utf8"));
const askUnsupported = JSON.parse(fs.readFileSync(askUnsupportedPath, "utf8"));

const failures = [];
const sources = Array.isArray(sourcesPayload.sources) ? sourcesPayload.sources : [];
const indexed = sources.filter((source) => source.indexed === true).length;

if (!/Goldborne Capital/i.test(page)) failures.push("homepage is missing Goldborne Capital branding");
if (/AI Dataroom Assistant/i.test(page)) failures.push("homepage still exposes old AI Dataroom Assistant heading");
if (/0 indexed sources/i.test(page)) failures.push("homepage still renders '0 indexed sources'");

if (health.ok !== true) failures.push("/api/health did not return ok=true");
if (!Number.isInteger(sourcesPayload.source_count)) failures.push("/api/sources missing numeric source_count");
if (!Number.isInteger(sourcesPayload.indexed_source_count)) failures.push("/api/sources missing numeric indexed_source_count");
if (sourcesPayload.source_count !== sources.length) failures.push(`source_count ${sourcesPayload.source_count} does not match sources.length ${sources.length}`);
if (sourcesPayload.indexed_source_count !== indexed) failures.push(`indexed_source_count ${sourcesPayload.indexed_source_count} does not match indexed sources ${indexed}`);
if (sources.length <= 0) failures.push("/api/sources returned no sources");

const creditAnswer = String(askCredit.answer || "");
const financialAnswer = String(askFinancial.answer || "");
const financialMissing = askFinancial.missing_information || askFinancial.missingInformation || [];
const financialType = askFinancial.answer_type || askFinancial.answerType;
const creditCitations = Array.isArray(askCredit.citations) ? askCredit.citations : [];
const unsupportedAnswer = String(askUnsupported.answer || "");
const unsupportedMissing = askUnsupported.missing_information || askUnsupported.missingInformation || [];
const unsupportedType = askUnsupported.answer_type || askUnsupported.answerType;

if (!creditAnswer || /lorem ipsum|hardcoded demo answer/i.test(creditAnswer)) failures.push("/api/ask credit response looks empty or hardcoded");
if (!creditCitations.length) failures.push("/api/ask credit response has no citations");
if (financialType !== "unknown") failures.push(`financial question with unavailable figures should be unknown, got ${financialType}`);
if (!/not available|cannot answer|unavailable/i.test(financialAnswer)) failures.push("unsupported financial response does not clearly say unavailable/unknown");
if (!Array.isArray(financialMissing) || !financialMissing.length) failures.push("unsupported financial response missing missing_information");
if (/[£$]\s*\d|\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b|\b\d+(?:\.\d+)?m\b/i.test(financialAnswer)) failures.push("unsupported financial response appears to invent numeric financials");
if (unsupportedType !== "unknown") failures.push(`unsupported question should be unknown, got ${unsupportedType}`);
if (!/not available|cannot answer|unavailable|missing/i.test(unsupportedAnswer)) failures.push("unsupported response does not clearly say unavailable/missing");
if (!Array.isArray(unsupportedMissing) || !unsupportedMissing.length) failures.push("unsupported response missing missing_information");

console.log(`Production API: ${sources.length} sources, ${indexed} indexed`);
console.log(`Ask credit: ${creditCitations.length} citations, confidence=${askCredit.confidence || "n/a"}`);
console.log(`Ask financial: type=${financialType}, missing=${Array.isArray(financialMissing) ? financialMissing.join(",") : "n/a"}`);
console.log(`Ask unsupported: type=${unsupportedType}, missing=${Array.isArray(unsupportedMissing) ? unsupportedMissing.join(",") : "n/a"}`);

if (failures.length) {
  for (const failure of failures) console.error(`FAIL: ${failure}`);
  process.exit(1);
}
NODE

echo "Production verification passed for $BASE_URL"
