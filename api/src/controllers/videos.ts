import type { Context } from "hono";
import { getVideo, listVideos } from "../db";
import type { App } from "../types";

export async function list(c: Context<App>) {
  const vids = await listVideos(c.env, c.get("auth").userId);
  return c.json(vids.map((v) => ({ id: v.id, job_id: v.job_id, bytes: Number(v.bytes), url: `/v1/videos/${v.id}`, created_at: v.created_at })));
}

export async function download(c: Context<App>) {
  const v = await getVideo(c.env, c.req.param("id")!, c.get("auth").userId);
  const obj = v && (await c.env.VIDEOS.get(v.r2_key));
  if (!obj) return c.json({ error: "not found" }, 404);
  return new Response(obj.body, { headers: { "Content-Type": "video/mp4", "Content-Length": String(obj.size) } });
}
