import type { Context } from "hono";
import { getJob, isUuid } from "../db";
import type { App } from "../types";
import { refuseNewJob } from "../job-limits";
import { forbidden, mayClep } from "./clep";

const PART_SIZE = 50 * 1024 * 1024;
const MAX_PARTS = 40;

type Completion = { upload_id?: string; parts?: { part: number; etag: string }[] };

export const captureKey = (userId: string, captureId: string) => `captures/${userId}/${captureId}.tar`;

const resumeUpload = (c: Context<App>, uploadId: string | undefined) => {
  const captureId = c.req.param("id")!;
  if (!isUuid(captureId) || !uploadId) return null;
  return c.env.VIDEOS.resumeMultipartUpload(captureKey(c.get("auth").userId, captureId), uploadId);
};

export async function start(c: Context<App>) {
  if (!mayClep(c)) return forbidden(c);
  const refused = await refuseNewJob(c, c.get("auth").userId, true);
  if (refused) return refused;
  const captureId = crypto.randomUUID();
  const upload = await c.env.VIDEOS.createMultipartUpload(captureKey(c.get("auth").userId, captureId));
  return c.json({ capture_id: captureId, upload_id: upload.uploadId, part_size: PART_SIZE }, 201);
}

export async function part(c: Context<App>) {
  const partNumber = Number(c.req.param("n"));
  const upload = resumeUpload(c, c.req.query("upload"));
  if (!upload || !Number.isInteger(partNumber) || partNumber < 1 || partNumber > MAX_PARTS || !c.req.raw.body) {
    return c.json({ error: `need a capture id, ?upload=<upload_id>, a part number 1–${MAX_PARTS} and a body` }, 400);
  }
  const uploaded = await upload.uploadPart(partNumber, c.req.raw.body);
  return c.json({ etag: uploaded.etag });
}

export async function complete(c: Context<App>) {
  const body: Completion = await c.req.json<Completion>().catch(() => ({}));
  const upload = resumeUpload(c, body.upload_id);
  if (!upload || !Array.isArray(body.parts) || !body.parts.length) {
    return c.json({ error: "need a capture id, upload_id and the parts sent" }, 400);
  }
  await upload.complete(body.parts.map((p) => ({ partNumber: p.part, etag: p.etag })));
  return c.json({ capture_id: c.req.param("id") });
}

export async function forJob(c: Context<App>) {
  const job = await getJob(c.env, c.req.param("id")!);
  const captureId = (job?.input as { capture?: string } | undefined)?.capture;
  const capture = job && captureId && isUuid(captureId) && (await c.env.VIDEOS.get(captureKey(job.user_id, captureId)));
  if (!capture) return c.json({ error: "capture not found (was the upload completed?)" }, 404);
  return new Response(capture.body, { headers: { "Content-Type": "application/x-tar", "Content-Length": String(capture.size) } });
}
