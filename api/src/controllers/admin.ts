import type { Context } from "hono";
import { createKey, createUser, revokeKey, userExists } from "../db";
import { ensureVm, vmStatus } from "../gcp";
import { ENGINES, type App, type Engine } from "../types";

// POST /admin/users  { email, name? }
export async function addUser(c: Context<App>) {
  const b = await c.req.json<{ email?: string; name?: string }>().catch(() => ({} as { email?: string; name?: string }));
  if (!b.email) return c.json({ error: "email is required" }, 400);
  try {
    return c.json(await createUser(c.env, b.email, b.name), 201);
  } catch {
    return c.json({ error: "a user with this email exists" }, 409);
  }
}

// POST /admin/users/:id/keys  { engines?: ["reels","motion"], label? } → the key is shown once
export async function addKey(c: Context<App>) {
  const b = await c.req.json<{ engines?: Engine[]; label?: string }>().catch(() => ({} as { engines?: Engine[]; label?: string }));
  const engines = b.engines ?? ENGINES;
  if (!engines.length || engines.some((e) => !ENGINES.includes(e))) return c.json({ error: `engines must be from ${ENGINES}` }, 400);
  if (!(await userExists(c.env, c.req.param("id")!))) return c.json({ error: "no such user" }, 404);
  return c.json(await createKey(c.env, c.req.param("id")!, engines, b.label), 201);
}

// DELETE /admin/keys/:id
export async function dropKey(c: Context<App>) {
  await revokeKey(c.env, c.req.param("id")!);
  return c.json({ ok: true });
}

// GET /admin/vm → { status } · POST /admin/vm/start → start it if stopped
export const vm = async (c: Context<App>) => c.json({ vm: c.env.GCP_VM, status: await vmStatus(c.env) });
export const vmStart = async (c: Context<App>) => c.json({ vm: c.env.GCP_VM, result: await ensureVm(c.env) });
