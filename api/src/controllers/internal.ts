import type { Context } from "hono";
import { claimJob, getJob, saveDraft, saveVideo, updateJob, type JobUpdate } from "../db";
import type { App } from "../types";

// POST /internal/jobs/:id/claim → 200 the job is now running and this worker owns it · 409 skip it (gone, taken, finished)
export async function claim(c: Context<App>) {
  const job = await claimJob(c.env, c.req.param("id")!);
  return job ? c.json({ ok: true, attempts: job.attempts }) : c.json({ error: "job is not queued" }, 409);
}

// PATCH /internal/jobs/:id  { status: done | failed, error?, cost_usd? }
export async function update(c: Context<App>) {
  const u = await c.req.json<JobUpdate>();
  if (u.status !== "done" && u.status !== "failed") return c.json({ error: "status must be done or failed (claim to start)" }, 400);
  await updateJob(c.env, c.req.param("id")!, u);
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
