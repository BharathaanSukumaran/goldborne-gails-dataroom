import type { Config, Context } from "@netlify/functions";
import { manifest } from "./_shared/data";

export default async (_req: Request, _context: Context) => {
  return Response.json({ company: manifest.company, sources: manifest.sources });
};

export const config: Config = { path: "/api/sources" };
