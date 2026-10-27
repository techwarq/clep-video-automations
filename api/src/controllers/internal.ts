import type { Context } from "hono";
import { claimJob, getJob, nextJob, saveDraft, saveVideo, setProgress, updateJob, type JobUpdate } from "../db";
import { recordExport } from "../usage";
import type { App } from "../types";

// POST /internal/jobs/:id/claim → 200 the job is now running and this worker owns it · 409 skip it (gone, taken, finished)
export async function claim(c: Context<App>) {
  const job = await claimJob(c.env, c.req.param("id")!);
  return job ? c.json({ ok: true, attempts: job.attempts }) : c.json({ error: "job is not queued" }, 409);
}

// POST /internal/jobs/next → 200 the oldest queued job, now running for this worker · 204 nothing queued.
// Local dev only (JOB_SOURCE=api on the worker); production workers pull the Cloudflare queue.
export async function next(c: Context<App>) {
  const j = await nextJob(c.env);
  if (!j) return c.body(null, 204);
  return c.json({ id: j.id, user_id: j.user_id, engine: j.engine, input: j.input,
    ...(j.draft_key ? { draft_key: j.draft_key } : {}) });
}

// PATCH /internal/jobs/:id  { status: done | failed, error?, cost_usd?, result? }
export async function update(c: Context<App>) {
  const u = await c.req.json<JobUpdate>().catch(() => ({} as JobUpdate));
  if (u.status !== "done" && u.status !== "failed") return c.json({ error: "status must be done or failed (claim to start)" }, 400);
  const updated = await updateJob(c.env, c.req.param("id")!, u);
  if (updated.length && u.status === "done" && typeof u.export_seconds === "number" && u.export_seconds > 0) {
    await recordExport(c.env, c.req.param("id")!, u.export_seconds);
  }
  return c.json({ ok: true });
}

export async function progress(c: Context<App>) {
  const body = await c.req.json<{ stage?: unknown; progress?: unknown }>().catch(() => ({} as { stage?: unknown; progress?: unknown }));
  const stage = typeof body.stage === "string" ? body.stage.slice(0, 40) : "";
  const percent = Math.round(Number(body.progress ?? 0));
  if (!stage || !Number.isFinite(percent) || percent < 0 || percent > 100) return c.json({ error: "stage and progress 0–100 are required" }, 400);
  await setProgress(c.env, c.req.param("id")!, stage, percent);
  return c.json({ ok: true });
}

// PUT /internal/jobs/:id/video  (raw mp4) → R2 videos/<user>/<job>.mp4 + videos row
export async function putVideo(c: Context<App>) {
  const job = await getJob(c.env, c.req.param("id")!);
  if (!job) return c.json({ error: "no such job" }, 404);
  const key = `videos/${job.user_id}/${job.id}.mp4`;
  const obj = await c.env.VIDEOS.put(key, c.req.raw.body, { httpMetadata: { contentType: "video/mp4" } });
  const video = await saveVideo(c.env, job, key, obj?.size ?? 0);
  return c.json({ video_id: video.id });
}

// PUT /internal/jobs/:id/draft  (raw tar.gz of the film source) → R2 drafts/<user>/<job>.tar.gz + drafts row
export async function putDraft(c: Context<App>) {
  const job = await getJob(c.env, c.req.param("id")!);
  if (!job) return c.json({ error: "no such job" }, 404);
  const key = `drafts/${job.user_id}/${job.id}.tar.gz`;
  const obj = await c.env.VIDEOS.put(key, c.req.raw.body, { httpMetadata: { contentType: "application/gzip" } });
  await saveDraft(c.env, job, key, obj?.size ?? 0);
  return c.json({ key });
}

// GET /internal/drafts/<r2 key>  — the VM fetches a draft to re-render it
export async function getDraftFile(c: Context<App>) {
  const obj = await c.env.VIDEOS.get(c.req.path.replace(/^\/internal\/drafts\//, ""));
  return obj ? new Response(obj.body, { headers: { "Content-Type": "application/gzip" } }) : c.json({ error: "not found" }, 404);
}
