import type { Config, Context } from "@netlify/functions";
import { indexedSourceCount, manifest, sourceCategories, sources } from "./_shared/data";

export default async (_req: Request, _context: Context) => {
  return Response.json({
    company: manifest.company,
    categories: sourceCategories,
    indexed_source_count: indexedSourceCount,
    source_count: sources.length,
    sources
  });
};

export const config: Config = { path: "/api/sources" };
