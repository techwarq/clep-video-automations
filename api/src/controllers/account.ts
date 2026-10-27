import type { Context } from "hono";
import { isAdminEmail } from "../access";
import { kitProblem, loadKit, saveKit, type BrandKit } from "../brand-kit";
import { getDraft, getJob, listJobs, requeue, videoForJob, wakeVm } from "../db";
import { listKeys } from "../keys";
import { refuseNewJob } from "../job-limits";
import { listProjects } from "../projects";
import { startJob } from "../start-job";
import type { App, Env, Job } from "../types";
import { monthlyUsage } from "../usage";

const clipView = async (env: Env, job: Job) => {
  const input = (job.input ?? {}) as Record<string, unknown>;
  const video = job.status === "done" ? await videoForJob(env, job.id) : null;
  return {
    id: job.id, name: input.name ?? input.kind ?? "clip", url: input.url ?? null, status: job.status,
    kind: input.capture ? "local" : input.kind ?? null, prompt: input.prompt ?? null,
    stage: job.stage, progress: job.progress, error: job.error,
    export_seconds: job.export_seconds === null ? null : Number(job.export_seconds),
    video: video ? { url: `/api/me/clips/${job.id}/video`, bytes: Number(video.bytes) } : null,
    created_at: job.created_at, updated_at: job.updated_at,
  };
};

export async function account(c: Context<App>) {
  const user = c.get("session");
  const [usage, keys] = await Promise.all([monthlyUsage(c.env, user.id), listKeys(c.env, user.id)]);
  return c.json({ user, usage, keys: keys.length, connected: keys.some((k) => k.last_used_at), is_admin: isAdminEmail(c.env, user.email) });
}

export async function clips(c: Context<App>) {
  const jobs = await listJobs(c.env, c.get("session").id, 50, "clep");
  return c.json({ clips: await Promise.all(jobs.map((job) => clipView(c.env, job))) });
}

export async function clip(c: Context<App>) {
  const job = await getJob(c.env, c.req.param("id")!, c.get("session").id);
  return job && job.engine === "clep" ? c.json(await clipView(c.env, job)) : c.json({ error: "not found" }, 404);
}

export async function clipVideo(c: Context<App>) {
  const job = await getJob(c.env, c.req.param("id")!, c.get("session").id);
  const video = job && job.engine === "clep" ? await videoForJob(c.env, job.id) : null;
  const object = video && (await c.env.VIDEOS.get(video.r2_key));
  if (!object) return c.json({ error: "not found" }, 404);
  return new Response(object.body, { headers: { "Content-Type": "video/mp4", "Content-Length": String(object.size) } });
}

export const projects = async (c: Context<App>) => c.json({ projects: await listProjects(c.env, c.get("session").id) });

export async function startClip(c: Context<App>) {
  const body = await c.req.json<Record<string, unknown>>().catch(() => ({} as Record<string, unknown>));
  if (body.capture !== undefined) return c.json({ error: "captures are started by the local recorder, not the dashboard" }, 400);
  const job = await startJob(c, { userId: c.get("session").id, keyId: null }, "clep", body);
  return job instanceof Response ? job : c.json(await clipView(c.env, job), 202);
}

export async function retryClip(c: Context<App>) {
  const user = c.get("session");
  const job = await getJob(c.env, c.req.param("id")!, user.id);
  if (!job || job.engine !== "clep") return c.json({ error: "not found" }, 404);
  if (job.status !== "failed") return c.json({ error: `only failed clips can be retried (this one is ${job.status})` }, 409);
  const refused = await refuseNewJob(c, { userId: user.id, keyId: null }, true);
  if (refused) return refused;
  await requeue(c.env, job, await getDraft(c.env, job.id));
  c.executionCtx.waitUntil(wakeVm(c.env));
  return c.json({ id: job.id, status: "queued" }, 202);
}

export const brandKit = async (c: Context<App>) => c.json({ kit: await loadKit(c.env, c.get("session").id) });

export async function saveBrandKit(c: Context<App>) {
  const body = await c.req.json<{ kit?: unknown }>().catch(() => ({} as { kit?: unknown }));
  const problem = kitProblem(body.kit);
  if (problem) return c.json({ error: problem }, 400);
  await saveKit(c.env, c.get("session").id, body.kit as BrandKit);
  return c.json({ kit: body.kit });
}
