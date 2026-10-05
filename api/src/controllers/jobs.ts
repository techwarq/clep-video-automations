import type { Context } from "hono";
import { getDraft, getJob, listJobs, requeue, videoForJob, wakeVm } from "../db";
import type { App, Env, Job } from "../types";

async function view(env: Env, j: Job) {
  const [video, draft] = await Promise.all([videoForJob(env, j.id), getDraft(env, j.id)]);
  return {
    id: j.id, engine: j.engine, input: j.input, status: j.status, attempts: j.attempts, error: j.error, cost_usd: Number(j.cost_usd),
    video: video ? { id: video.id, url: `/v1/videos/${video.id}` } : null, has_draft: !!draft,
    created_at: j.created_at, updated_at: j.updated_at,
  };
}

export async function list(c: Context<App>) {
  const jobs = await listJobs(c.env, c.get("auth").userId);
  return c.json(await Promise.all(jobs.map((j) => view(c.env, j))));
}

export async function get(c: Context<App>) {
  const job = await getJob(c.env, c.req.param("id")!, c.get("auth").userId);
  return job ? c.json(await view(c.env, job)) : c.json({ error: "not found" }, 404);
}

// POST /v1/jobs/:id/retry — a failed job runs again; with a saved draft it only re-renders (no model spend)
export async function retry(c: Context<App>) {
  const job = await getJob(c.env, c.req.param("id")!, c.get("auth").userId);
  if (!job) return c.json({ error: "not found" }, 404);
  if (job.status !== "failed") return c.json({ error: `only failed jobs can be retried (this one is ${job.status})` }, 409);
  const draft = await getDraft(c.env, job.id);
  await requeue(c.env, job, draft);
  c.executionCtx.waitUntil(wakeVm(c.env));
  return c.json({ id: job.id, status: "queued", from_draft: !!draft }, 202);
}
