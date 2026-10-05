import type { Context } from "hono";
import { createJob, wakeVm } from "../db";
import type { App, Engine } from "../types";

type Validate = (b: Record<string, unknown>) => string | null;

const VALIDATE: Record<Engine, Validate> = {
  // POST /v1/reels  { prompt, style?, tts? }
  reels: (b) => (typeof b.prompt === "string" && b.prompt ? null : "prompt is required"),
  // POST /v1/motion  { url, request, seconds? }
  motion: (b) => (typeof b.url === "string" && typeof b.request === "string" ? null : "url and request are required"),
};

export const create = (engine: Engine) => async (c: Context<App>) => {
  const auth = c.get("auth");
  if (!auth.engines.includes(engine)) return c.json({ error: `this key may not use ${engine}` }, 403);
  const body = await c.req.json<Record<string, unknown>>().catch(() => ({}));
  const err = VALIDATE[engine](body);
  if (err) return c.json({ error: err }, 400);
  const job = await createJob(c.env, auth, engine, body);
  c.executionCtx.waitUntil(wakeVm(c.env));
  return c.json({ id: job.id, status: job.status }, 202);
};
