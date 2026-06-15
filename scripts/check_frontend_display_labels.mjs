import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const files = [
  "frontend/app/page.tsx",
  "frontend/components/chat-panel.tsx",
  "frontend/components/source-browser.tsx",
  "frontend/components/source-card.tsx"
];

const rawLabels = [
  "company_profile",
  "financial_filings",
  "charges_register",
  "ownership_management",
  "news_events",
  "industry_context",
  "source_count",
  "indexed_count",
  "indexed_source_count",
  "usedInAnswers",
  "used_in_answers",
  "reviewed=",
  "reviewed: true",
  "reviewed: false",
  "sourceId",
  "source_id",
  "workspaceId",
  "workspace_id",
  "periodEnd",
  "period_end",
  "reportedOrComputed",
  "reported_or_computed",
  "processing_status",
  "source_status",
  "included_reason",
  "local_path",
  "financial_facts",
  "fieldIntent",
  "field_intent",
  "resolvedChargeCode",
  "resolved_charge_code"
];

const failures = [];

for (const file of files) {
  const text = readFileSync(join(ROOT, file), "utf8");

  if (/Object\.entries\([^)]*\)\.map/.test(text)) {
    failures.push(`${file}: generic Object.entries rendering`);
  }

  for (const rawLabel of rawLabels) {
    const escaped = escapeRegExp(rawLabel);
    const visibleText = new RegExp(`>[^<>{}\\n]*${escaped}[^<>{}\\n]*<`);
    const visibleAttribute = new RegExp(`(?:aria-label|title|placeholder)=["'][^"']*${escaped}[^"']*["']`);
    const stringChild = new RegExp(`\\{["']${escaped}["']\\}`);

    if (visibleText.test(text) || visibleAttribute.test(text) || stringChild.test(text)) {
      failures.push(`${file}: visible raw label "${rawLabel}"`);
    }
  }
}

if (failures.length) {
  console.error("Frontend display-label check failed:");
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exit(1);
}

console.log("Frontend display-label check passed.");

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
