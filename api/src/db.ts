import { neon } from "@neondatabase/serverless";
import { ensureVm } from "./gcp";
import type { Auth, Draft, Engine, Env, Job, JobStatus, Video } from "./types";

// Neon over HTTP: one round trip per query, nothing to pool inside the Worker
const db = (env: Env) => neon(env.DATABASE_URL);

// a malformed id is "not found", not a Postgres error
const isUuid = (s: string) => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s);

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

export async function createKey(env: Env, userId: string, engines: Engine[], label?: string) {
  const raw = new Uint8Array(32); crypto.getRandomValues(raw);
  const key = "va_" + btoa(String.fromCharCode(...raw)).replace(/[+/=]/g, (c) => ({ "+": "-", "/": "_", "=": "" })[c]!);
  const [row] = await db(env)`
    INSERT INTO access_keys (user_id, key_hash, prefix, label, engines)
    VALUES (${userId}, ${await sha256(key)}, ${key.slice(0, 10)}, ${label ?? null}, ${engines})
    RETURNING id, prefix, label, engines, created_at`;
  return { ...row, key };  // the only time the key itself is returned
}

export const revokeKey = async (env: Env, keyId: string) =>
  isUuid(keyId) && db(env)`UPDATE access_keys SET revoked_at = now() WHERE id = ${keyId}`;

export async function findKey(env: Env, key: string): Promise<Auth | null> {
  if (!key) return null;
  const [r] = await db(env)`SELECT id, user_id, engines FROM access_keys WHERE key_hash = ${await sha256(key)} AND revoked_at IS NULL`;
  return r ? { userId: r.user_id, keyId: r.id, engines: r.engines } : null;
}

// ---- jobs
// after queueing: mark work pending and make sure the render VM is up. Never fails the request.
export async function wakeVm(env: Env) {
  await env.STATE.put("pending", String(Date.now()));
  await ensureVm(env).catch((e) => console.error("wake VM:", e));
}

// the every-minute safety net: nothing pending → one KV read, no database, no GCP call
export async function sweep(env: Env) {
  if (!(await env.STATE.get("pending"))) return;
  const queued = (await db(env)`SELECT 1 FROM jobs WHERE status = 'queued' LIMIT 1`).length > 0;
  if (!queued) return env.STATE.delete("pending");
  await ensureVm(env).catch((e) => console.error("sweep VM:", e));
}

export async function createJob(env: Env, auth: Auth, engine: Engine, input: unknown): Promise<Job> {
  const [job] = await db(env)`
    INSERT INTO jobs (user_id, key_id, engine, input) VALUES (${auth.userId}, ${auth.keyId}, ${engine}, ${JSON.stringify(input)}::jsonb)
    RETURNING *` as Job[];
  try {
    await env.JOBS.send({ id: job.id, user_id: job.user_id, engine, input });
  } catch (e) {
    // the row exists but no worker will ever see it: fail it visibly instead of leaving it queued forever
    await updateJob(env, job.id, { status: "failed", error: `could not queue the job: ${e}` });
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

export const listJobs = async (env: Env, userId: string, limit = 50) =>
  (await db(env)`SELECT * FROM jobs WHERE user_id = ${userId} ORDER BY created_at DESC LIMIT ${limit}`) as Job[];

export type JobUpdate = { status: JobStatus; error?: string; cost_usd?: number };

// cost_usd from the VM is this attempt's spend: it is added to what earlier attempts cost
export const updateJob = (env: Env, jobId: string, u: JobUpdate) =>
  db(env)`
    UPDATE jobs SET status = ${u.status},
      error = ${u.status === "failed" ? u.error ?? "failed" : null},
      cost_usd = cost_usd + ${u.cost_usd ?? 0},
      attempts = attempts + ${u.status === "running" ? 1 : 0},
      updated_at = now()
    WHERE id = ${jobId}`;

export async function requeue(env: Env, job: Job, draft: Draft | null) {
  await db(env)`UPDATE jobs SET status = 'queued', error = NULL, updated_at = now() WHERE id = ${job.id}`;
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
