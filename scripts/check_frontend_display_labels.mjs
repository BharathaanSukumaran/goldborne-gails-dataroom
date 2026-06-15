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
  "source_count",
  "indexed_count",
  "usedInAnswers",
  "reviewed=",
  "workspaceId",
  "sourceId",
  "periodEnd",
  "reportedOrComputed"
];

const allowedInternalTokens = new Map([
  ["frontend/components/source-card.tsx", new Set(["sourceId"])]
]);

const failures = [];

for (const file of files) {
  const text = readFileSync(join(ROOT, file), "utf8");
  for (const rawLabel of rawLabels) {
    if (text.includes(rawLabel) && !allowedInternalTokens.get(file)?.has(rawLabel)) {
      failures.push(`${file}: raw label "${rawLabel}"`);
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
