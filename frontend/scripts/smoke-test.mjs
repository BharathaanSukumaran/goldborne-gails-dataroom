import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const page = readFileSync(join(root, "app", "page.tsx"), "utf8");
const chat = readFileSync(join(root, "components", "chat-panel.tsx"), "utf8");
const api = readFileSync(join(root, "lib", "api.ts"), "utf8");
const browser = readFileSync(join(root, "components", "source-browser.tsx"), "utf8");

const failures = [];
if (!page.includes("Goldborne Capital")) failures.push("home page missing Goldborne Capital");
if (!page.includes("GAIL&apos;S Limited")) failures.push("home page missing active dataroom");
if (!chat.includes("textarea")) failures.push("chat input textarea missing");
if (!chat.includes("suggestedQuestions")) failures.push("suggested prompts missing");
if (!page.includes("View dataroom") || !page.includes("Hide dataroom")) failures.push("dataroom open/close controls missing");
if (!browser.includes('label: "Documents"') || !browser.includes('label: "Reviewed facts"')) failures.push("drawer tabs missing");
const secretEnvToken = ["OPENAI", "API", "KEY"].join("_");
if ((page + chat + api + browser).includes(secretEnvToken) || /from ["']openai|new OpenAI/.test(page + chat + api + browser)) failures.push("frontend references OpenAI secret/client");
if (!api.includes('"/ask"')) failures.push("frontend does not call /api ask path");

if (failures.length) {
  console.error("Frontend smoke test failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}
console.log("Frontend smoke test passed.");
