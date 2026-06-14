import type { Config, Context } from "@netlify/functions";

export default async (_req: Request, _context: Context) => {
  return Response.json({ ok: true, service: "gails-dataroom-netlify" });
};

export const config: Config = { path: "/api/health" };
