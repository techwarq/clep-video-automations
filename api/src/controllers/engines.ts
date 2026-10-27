import type { Context } from "hono";
import { startJob } from "../start-job";
import type { App, Engine } from "../types";

export const create = (engine: Engine) => async (c: Context<App>) => {
  const auth = c.get("auth");
  if (!auth.engines.includes(engine)) return c.json({ error: `this key may not use ${engine}` }, 403);
  const body = await c.req.json<Record<string, unknown>>().catch(() => ({}));
  const job = await startJob(c, auth, engine, body);
  return job instanceof Response ? job : c.json({ id: job.id, status: job.status }, 202);
};
