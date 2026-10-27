import type { Context } from "hono";
import { loadKit, withKit } from "./brand-kit";
import { createJob, wakeVm } from "./db";
import { inputProblem } from "./job-input";
import { refuseNewJob } from "./job-limits";
import type { App, Engine, Job, Owner } from "./types";

export async function startJob(c: Context<App>, owner: Owner, engine: Engine, body: unknown): Promise<Job | Response> {
  const problem = inputProblem(engine, body);
  if (problem) return c.json({ error: problem }, 400);
  const refused = await refuseNewJob(c, owner.userId, engine === "clep");
  if (refused) return refused;
  const input = engine === "clep" ? withKit(body as Record<string, unknown>, await loadKit(c.env, owner.userId)) : body;
  const job = await createJob(c.env, owner, engine, input);
  c.executionCtx.waitUntil(wakeVm(c.env));
  return job;
}
