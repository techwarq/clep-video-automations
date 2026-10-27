// The Clep plugin's API (`bin/clep` in techwarq/clep-plugin): /api/health, /api/features, /api/clips, /api/jobs.
// Same jobs, keys and storage as /v1 — only the shapes the plugin expects differ:
//   status queued | recording | done | error · the finished clip at `out` · the key in X-API-Key.
import type { Context } from "hono";
import { createJob, getJob, listJobs, videoForJob, wakeVm } from "../db";
import { tooManyActiveJobs } from "../job-limits";
import { isPublicWebUrl } from "../public-url";
import { startJob } from "../start-job";
import type { App, Env, Job } from "../types";

const STATUS: Record<Job["status"], string> = { queued: "queued", running: "recording", done: "done", failed: "error" };

async function view(env: Env, j: Job) {
  const input = (j.input ?? {}) as Record<string, unknown>;
  const video = j.status === "done" ? await videoForJob(env, j.id) : null;
  return {
    id: j.id, job_id: j.id, status: STATUS[j.status],
    name: input.name ?? input.kind ?? "clip", kind: input.kind ?? null, url: input.url ?? null, prompt: input.prompt ?? null,
    out: video ? `/api/jobs/${j.id}/video` : null, bytes: video ? Number(video.bytes) : null,
    stage: j.stage, progress: j.progress,
    error: j.error, attempts: j.attempts, created_at: j.created_at, updated_at: j.updated_at,
  };
}

export const mayClep = (c: Context<App>) => c.get("auth").engines.includes("clep");
export const forbidden = (c: Context<App>) => c.json({ error: "this key may not make clips (clep is not among its engines)" }, 403);

// GET /api/health (no key)
export const health = (c: Context<App>) => c.json({ ok: true, service: "clep" });

// POST /api/clips  { prompt } or { url, name?, kind?, query?, steps?, sections?, duration?, … } → { job_id }
export async function clip(c: Context<App>) {
  if (!mayClep(c)) return forbidden(c);
  const body = await c.req.json<Record<string, unknown>>().catch(() => ({}));
  const job = await startJob(c, c.get("auth"), "clep", body);
  return job instanceof Response ? job : c.json({ job_id: job.id, id: job.id, status: "queued" }, 202);
}

// GET /api/jobs → { jobs: [...] } (clips only, newest first)
export async function jobs(c: Context<App>) {
  const rows = await listJobs(c.env, c.get("auth").userId, 50, "clep");
  return c.json({ jobs: await Promise.all(rows.map((j) => view(c.env, j))) });
}

// GET /api/jobs/:id
export async function job(c: Context<App>) {
  const j = await getJob(c.env, c.req.param("id")!, c.get("auth").userId);
  if (!j || j.engine !== "clep") return c.json({ error: "not found" }, 404);
  return c.json(await view(c.env, j));
}

// GET /api/jobs/:id/video → the mp4
export async function video(c: Context<App>) {
  const j = await getJob(c.env, c.req.param("id")!, c.get("auth").userId);
  const v = j && j.engine === "clep" ? await videoForJob(c.env, j.id) : null;
  const obj = v && (await c.env.VIDEOS.get(v.r2_key));
  if (!obj) return c.json({ error: "not found" }, 404);
  return new Response(obj.body, { headers: { "Content-Type": "video/mp4", "Content-Length": String(obj.size) } });
}

// GET /api/features?url=… → { url, count, features: [{ name, has_input, has_button, button_label, states, … }] }
// The page is opened in a real browser by the renderer (data-clep is usually rendered client-side), so this is a
// short job; the request waits for it. A renderer that is still starting up answers 504 — run scan again.
const SCAN_WAIT_MS = 55_000;
export async function features(c: Context<App>) {
  if (!mayClep(c)) return forbidden(c);
  const url = c.req.query("url") ?? "";
  if (!isPublicWebUrl(url)) return c.json({ error: "url must be a public http(s) address (record localhost pages with the local recorder)" }, 400);
  const busy = await tooManyActiveJobs(c, c.get("auth").userId);
  if (busy) return busy;
  const job = await createJob(c.env, c.get("auth"), "clep", { scan: url });
  c.executionCtx.waitUntil(wakeVm(c.env));
  const deadline = Date.now() + SCAN_WAIT_MS;
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 1000));
    const j = await getJob(c.env, job.id);
    if (j?.status === "done") return c.json(j.result ?? { url, count: 0, features: [] });
    if (j?.status === "failed") return c.json({ error: j.error ?? "scan failed" }, 502);
  }
  return c.json({ error: "the renderer is still starting up — run the scan again in a minute" }, 504);
}
