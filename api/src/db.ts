import { neon } from "@neondatabase/serverless";
import { ensureVm } from "./gcp";
import { useLocalDatabaseWhenAsked } from "./local-database";
import type { Draft, Engine, Env, Job, JobStatus, Owner, Video } from "./types";

// Neon over HTTP: one round trip per query, nothing to pool inside the Worker
export const db = (env: Env) => {
  useLocalDatabaseWhenAsked(env.DATABASE_URL);
  return neon(env.DATABASE_URL);
};

// a malformed id is "not found", not a Postgres error
export const isUuid = (s: string) => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s);

export async function sha256(s: string): Promise<string> {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// ---- users + access keys
export async function createUser(env: Env, email: string, name?: string) {
  const [u] = await db(env)`INSERT INTO users (email, name) VALUES (${email}, ${name ?? null}) RETURNING *`;
  return u;
}

export const userExists = async (env: Env, userId: string) =>
  isUuid(userId) && (await db(env)`SELECT 1 FROM users WHERE id = ${userId}`).length > 0;

export function randomToken(prefix: string): string {
  const raw = new Uint8Array(32); crypto.getRandomValues(raw);
  return prefix + btoa(String.fromCharCode(...raw)).replace(/[+/=]/g, (c) => ({ "+": "-", "/": "_", "=": "" })[c]!);
}

// ---- jobs
// after queueing: mark work pending and make sure the render VM is up. Never fails the request.
export async function wakeVm(env: Env) {
  await env.STATE.put("pending", String(Date.now()));
  await ensureVm(env).catch((e) => console.error("wake VM:", e));
}

// A job runs once per request: the worker acks its message on pickup, so nothing is ever redelivered.
// A render that dies with its VM is failed here (not re-run); POST /v1/jobs/:id/retry is the only way to run it again.
const STALE_RUNNING = "90 minutes";
export const failStaleRunning = (env: Env) =>
  db(env)`
    UPDATE jobs SET status = 'failed', updated_at = now(),
      error = 'the render was interrupted (the worker stopped mid-job) — retry to run it again'
    WHERE status = 'running' AND updated_at < now() - ${STALE_RUNNING}::interval
    RETURNING id`;

// the every-minute safety net: nothing pending → one KV read, no database, no GCP call
export async function sweep(env: Env, scheduledTime = Date.now()) {
  if (new Date(scheduledTime).getUTCMinutes() % 15 === 0) await failStaleRunning(env).catch((e) => console.error("stale jobs:", e));
  if (!(await env.STATE.get("pending"))) return;
  const queued = (await db(env)`SELECT 1 FROM jobs WHERE status = 'queued' LIMIT 1`).length > 0;
  if (!queued) return env.STATE.delete("pending");
  await ensureVm(env).catch((e) => console.error("sweep VM:", e));
}

export async function createJob(env: Env, owner: Owner, engine: Engine, input: unknown): Promise<Job> {
  const [job] = await db(env)`
    INSERT INTO jobs (user_id, key_id, engine, input) VALUES (${owner.userId}, ${owner.keyId}, ${engine}, ${JSON.stringify(input)}::jsonb)
    RETURNING *` as Job[];
  try {
    await env.JOBS.send({ id: job.id, user_id: job.user_id, engine, input });
  } catch (e) {
    // the row exists but no worker will ever see it: fail it visibly instead of leaving it queued forever
    await db(env)`UPDATE jobs SET status = 'failed', error = ${`could not queue the job: ${e}`}, updated_at = now() WHERE id = ${job.id}`;
    throw e;
  }
  return job;
}

export async function getJob(env: Env, jobId: string, userId?: string): Promise<Job | null> {
  if (!isUuid(jobId)) return null;
  const rows = userId
    ? await db(env)`SELECT * FROM jobs WHERE id = ${jobId} AND user_id = ${userId}`
    : await db(env)`SELECT * FROM jobs WHERE id = ${jobId}`;
  return (rows[0] as Job) ?? null;
}

// a user's jobs, newest first; feature scans (input.scan) are lookups, not videos, so they are left out
export const listJobs = async (env: Env, userId: string, limit = 50, engine?: Engine) =>
  (engine
    ? await db(env)`SELECT * FROM jobs WHERE user_id = ${userId} AND engine = ${engine} AND NOT (input ? 'scan')
                    ORDER BY created_at DESC LIMIT ${limit}`
    : await db(env)`SELECT * FROM jobs WHERE user_id = ${userId} AND NOT (input ? 'scan')
                    ORDER BY created_at DESC LIMIT ${limit}`) as Job[];

export type JobUpdate = { status: "done" | "failed"; error?: string; cost_usd?: number; result?: unknown; export_seconds?: number };

// The worker takes a job: queued → running, atomically. Anything else (gone, already taken, done, failed) → null,
// and the worker skips it — so a stray or duplicate message can never start a second run.
export async function claimJob(env: Env, jobId: string): Promise<Job | null> {
  if (!isUuid(jobId)) return null;
  const [j] = await db(env)`
    UPDATE jobs SET status = 'running', attempts = attempts + 1, error = NULL, stage = 'starting', progress = 0, updated_at = now()
    WHERE id = ${jobId} AND status = 'queued' RETURNING *`;
  return (j as Job) ?? null;
}

// running → done | failed. cost_usd from the VM is this attempt's spend: added to what earlier attempts cost.
// Only a running job can finish, so a late report can't overwrite a job that was failed or retried meanwhile.
export const updateJob = (env: Env, jobId: string, u: JobUpdate) =>
  db(env)`
    UPDATE jobs SET status = ${u.status},
      error = ${u.status === "failed" ? u.error ?? "failed" : null},
      cost_usd = cost_usd + ${u.cost_usd ?? 0},
      result = ${u.result === undefined ? null : JSON.stringify(u.result)}::jsonb,
      export_seconds = ${u.status === "done" ? u.export_seconds ?? null : null},
      stage = ${u.status}, progress = ${u.status === "done" ? 100 : 0},
      updated_at = now()
    WHERE id = ${jobId} AND status = 'running' RETURNING id`;

export const setProgress = (env: Env, jobId: string, stage: string, progress: number) =>
  db(env)`UPDATE jobs SET stage = ${stage}, progress = ${progress}, updated_at = now()
          WHERE id = ${jobId} AND status = 'running'`;

// Local dev only (a `wrangler dev` queue never reaches the worker): hand out the oldest queued job, claimed in the
// same statement (queued → running), so two local workers can never take the same one.
export async function nextJob(env: Env): Promise<(Job & { draft_key: string | null }) | null> {
  const [j] = await db(env)`
    UPDATE jobs SET status = 'running', attempts = attempts + 1, error = NULL, stage = 'starting', progress = 0, updated_at = now()
    WHERE id = (SELECT id FROM jobs WHERE status = 'queued' ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED)
    RETURNING *, (SELECT r2_key FROM drafts WHERE drafts.job_id = jobs.id) AS draft_key`;
  return (j as Job & { draft_key: string | null }) ?? null;
}

export async function requeue(env: Env, job: Job, draft: Draft | null) {
  await db(env)`UPDATE jobs SET status = 'queued', error = NULL, stage = NULL, progress = 0, updated_at = now() WHERE id = ${job.id}`;
  await env.JOBS.send({ id: job.id, user_id: job.user_id, engine: job.engine, input: job.input,
    ...(draft ? { draft_key: draft.r2_key } : {}) });
}

// ---- drafts + videos
export async function getDraft(env: Env, jobId: string): Promise<Draft | null> {
  const [d] = await db(env)`SELECT * FROM drafts WHERE job_id = ${jobId}`;
  return (d as Draft) ?? null;
}

export const saveDraft = (env: Env, job: Job, r2Key: string, bytes: number) =>
  db(env)`
    INSERT INTO drafts (job_id, user_id, r2_key, bytes) VALUES (${job.id}, ${job.user_id}, ${r2Key}, ${bytes})
    ON CONFLICT (job_id) DO UPDATE SET r2_key = excluded.r2_key, bytes = excluded.bytes, updated_at = now()`;

export async function saveVideo(env: Env, job: Job, r2Key: string, bytes: number): Promise<Video> {
  const [v] = await db(env)`
    INSERT INTO videos (job_id, user_id, r2_key, bytes) VALUES (${job.id}, ${job.user_id}, ${r2Key}, ${bytes}) RETURNING *`;
  return v as Video;
}

export async function getVideo(env: Env, videoId: string, userId: string): Promise<Video | null> {
  if (!isUuid(videoId)) return null;
  const [v] = await db(env)`SELECT * FROM videos WHERE id = ${videoId} AND user_id = ${userId}`;
  return (v as Video) ?? null;
}

export async function videoForJob(env: Env, jobId: string): Promise<Video | null> {
  const [v] = await db(env)`SELECT * FROM videos WHERE job_id = ${jobId} ORDER BY created_at DESC LIMIT 1`;
  return (v as Video) ?? null;
}

export const listVideos = async (env: Env, userId: string, limit = 50) =>
  (await db(env)`SELECT * FROM videos WHERE user_id = ${userId} ORDER BY created_at DESC LIMIT ${limit}`) as Video[];
