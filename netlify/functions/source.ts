import type { Config, Context } from "@netlify/functions";
import { sourceById } from "./_shared/data";

export default async (_req: Request, context: Context) => {
  const source = sourceById(context.params.source_id);
  if (!source) return Response.json({ detail: "source_id not found" }, { status: 404 });
  return Response.json(source);
};

export const config: Config = { path: "/api/sources/:source_id" };
