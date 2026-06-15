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
ask_missing_json="$tmp_dir/ask_missing.json"
ask_empty_json="$tmp_dir/ask_empty.json"
bundle_urls="$tmp_dir/bundle_urls.txt"
bundle_js="$tmp_dir/frontend_bundle.js"

homepage_status="$(curl -sS -L -w "%{http_code}" "$BASE_URL/" -o "$page_html")"
if [ "$homepage_status" != "200" ]; then
  echo "FAIL: homepage returned HTTP $homepage_status" >&2
  exit 1
fi

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

missing_status="$(curl -sS -L -w "%{http_code}" "$BASE_URL/api/ask" \
  -H "Content-Type: application/json" \
  -d '{}' \
  -o "$ask_missing_json")"

empty_status="$(curl -sS -L -w "%{http_code}" "$BASE_URL/api/ask" \
  -H "Content-Type: application/json" \
  -d '{"workspaceId":"gails-limited","question":""}' \
  -o "$ask_empty_json")"

node - "$page_html" "$health_json" "$sources_json" "$ask_credit_json" "$ask_financial_json" "$ask_unsupported_json" "$missing_status" "$empty_status" "$ask_missing_json" "$ask_empty_json" <<'NODE'
const fs = require("node:fs");
const [
  pagePath,
  healthPath,
  sourcesPath,
  askCreditPath,
  askFinancialPath,
  askUnsupportedPath,
  missingStatus,
  emptyStatus,
  askMissingPath,
  askEmptyPath,
] = process.argv.slice(2);
const page = fs.readFileSync(pagePath, "utf8");
const health = JSON.parse(fs.readFileSync(healthPath, "utf8"));
const sourcesPayload = JSON.parse(fs.readFileSync(sourcesPath, "utf8"));
const askCredit = JSON.parse(fs.readFileSync(askCreditPath, "utf8"));
const askFinancial = JSON.parse(fs.readFileSync(askFinancialPath, "utf8"));
const askUnsupported = JSON.parse(fs.readFileSync(askUnsupportedPath, "utf8"));
const askMissingBody = fs.readFileSync(askMissingPath, "utf8");
const askEmptyBody = fs.readFileSync(askEmptyPath, "utf8");

const failures = [];
const sources = Array.isArray(sourcesPayload.sources) ? sourcesPayload.sources : [];
const indexed = sources.filter((source) => source.indexed === true).length;

if (!/Goldborne Capital/i.test(page)) failures.push("homepage is missing Goldborne Capital branding");
if (/AI Dataroom Assistant/i.test(page)) failures.push("homepage still exposes old AI Dataroom Assistant heading");
if (/0 indexed sources/i.test(page)) failures.push("homepage still renders '0 indexed sources'");

if (health.ok !== true) failures.push("/api/health did not return ok=true");
if (!Number.isInteger(sourcesPayload.source_count)) failures.push("/api/sources missing numeric source_count");
if (!Number.isInteger(sourcesPayload.indexed_source_count)) failures.push("/api/sources missing numeric indexed_source_count");
if (sourcesPayload.source_count <= 0) failures.push("/api/sources source_count is not > 0");
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

for (const [label, status, body] of [
  ["missing query", missingStatus, askMissingBody],
  ["empty query", emptyStatus, askEmptyBody],
]) {
  const code = Number(status);
  if (!Number.isInteger(code) || code < 200 || code >= 500) {
    failures.push(`/api/ask ${label} returned server error/status ${status}`);
  }
  if (/internal server error|traceback|unhandled|exception/i.test(body)) {
    failures.push(`/api/ask ${label} response exposes a server error`);
  }
}

console.log(`Production API: ${sources.length} sources, ${indexed} indexed`);
console.log(`Ask credit: ${creditCitations.length} citations, confidence=${askCredit.confidence || "n/a"}`);
console.log(`Ask financial: type=${financialType}, missing=${Array.isArray(financialMissing) ? financialMissing.join(",") : "n/a"}`);
console.log(`Ask unsupported: type=${unsupportedType}, missing=${Array.isArray(unsupportedMissing) ? unsupportedMissing.join(",") : "n/a"}`);
console.log(`Ask validation errors: missing=${missingStatus}, empty=${emptyStatus}`);

if (failures.length) {
  for (const failure of failures) console.error(`FAIL: ${failure}`);
  process.exit(1);
}
NODE

node - "$BASE_URL" "$page_html" > "$bundle_urls" <<'NODE'
const fs = require("node:fs");
const [baseUrl, pagePath] = process.argv.slice(2);
const page = fs.readFileSync(pagePath, "utf8");
const urls = new Set();
const addUrl = (raw) => {
  if (!raw || !/\.js(?:[?#].*)?$/i.test(raw)) return;
  urls.add(new URL(raw, `${baseUrl}/`).toString());
};

for (const match of page.matchAll(/<script\b[^>]*\bsrc=["']([^"']+)["'][^>]*>/gi)) {
  addUrl(match[1]);
}
for (const match of page.matchAll(/\b(?:src|href)=["']([^"']*\/_next\/static\/[^"']+\.js(?:[?#][^"']*)?)["']/gi)) {
  addUrl(match[1]);
}

for (const url of urls) console.log(url);
NODE

: > "$bundle_js"
while IFS= read -r js_url; do
  [ -n "$js_url" ] || continue
  curl -fsSL "$js_url" >> "$bundle_js"
  printf '\n' >> "$bundle_js"
done < "$bundle_urls"

node - "$bundle_urls" "$bundle_js" <<'NODE'
const fs = require("node:fs");
const urls = fs.readFileSync(process.argv[2], "utf8").trim().split(/\n+/).filter(Boolean);
const bundle = fs.readFileSync(process.argv[3], "utf8");
const failures = [];

if (!urls.length) failures.push("homepage did not reference any frontend JavaScript bundles");
if (/\bOPENAI_API_KEY\b/.test(bundle)) failures.push("frontend bundle exposes OPENAI_API_KEY");
if (/api\.openai\.com\/v1/i.test(bundle)) failures.push("frontend bundle appears to call OpenAI directly");

console.log(`Frontend bundle scan: ${urls.length} JavaScript assets`);

if (failures.length) {
  for (const failure of failures) console.error(`FAIL: ${failure}`);
  process.exit(1);
}
NODE

echo "Production verification passed for $BASE_URL"
