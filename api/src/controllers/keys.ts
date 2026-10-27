import type { Context } from "hono";
import { EXPIRY_DAYS, issueKey, listKeys, revokeOwnKey, rotateKey, updateKey, type KeySettings } from "../keys";
import { limitsOf, MAX_ACTIVE_KEYS } from "../plans";
import type { App, Plan } from "../types";
import { monthlyUsage } from "../usage";

const MAX_LABEL = 60;
const DEFAULT_LABEL = "Untitled key";

type KeyBody = { label?: unknown; expires_in_days?: unknown; disabled?: unknown };
type Parsed = { settings: KeySettings; expiresInDays: number | null };

function parse(body: KeyBody): Parsed | string {
  const settings: KeySettings = {};
  if (body.label !== undefined) {
    if (typeof body.label !== "string" || body.label.trim().length > MAX_LABEL) return `label must be text up to ${MAX_LABEL} characters`;
    settings.label = body.label.trim() || DEFAULT_LABEL;
  }
  if (body.disabled !== undefined) {
    if (typeof body.disabled !== "boolean") return "disabled must be true or false";
    settings.disabled = body.disabled;
  }
  const days = body.expires_in_days ?? null;
  if (days !== null && !EXPIRY_DAYS.includes(days as number)) return `expires_in_days must be one of ${EXPIRY_DAYS.join(", ")}, or null for no expiration`;
  return { settings, expiresInDays: days as number | null };
}

const readBody = (c: Context<App>) => c.req.json<KeyBody>().catch(() => ({} as KeyBody));

const view = (row: Record<string, unknown>) => ({
  id: row.id, label: row.label, prefix: row.prefix, last4: row.last4,
  disabled: row.disabled_at !== null, expires_at: row.expires_at,
  expired: row.expires_at !== null && new Date(row.expires_at as string).getTime() <= Date.now(),
  used_seconds: Number(row.used_seconds ?? 0),
  created_at: row.created_at, last_used_at: row.last_used_at,
});

export async function list(c: Context<App>) {
  const user = c.get("session");
  const [keys, usage] = await Promise.all([listKeys(c.env, user.id), monthlyUsage(c.env, user.id)]);
  const limits = limitsOf(usage.plan);
  return c.json({
    keys: keys.map(view),
    plan: { name: usage.plan, requests_per_minute: limits.requestsPerMinute, active_jobs: limits.activeJobs, export_minutes: limits.exportMinutes },
  });
}

export async function create(c: Context<App>) {
  const user = c.get("session");
  const parsed = parse(await readBody(c));
  if (typeof parsed === "string") return c.json({ error: parsed }, 400);
  const created = await issueKey(c.env, user.id, ["clep"], parsed.settings.label ?? DEFAULT_LABEL, parsed.expiresInDays, MAX_ACTIVE_KEYS);
  if (!created) return c.json({ error: `you have ${MAX_ACTIVE_KEYS} active keys: revoke some you no longer use first` }, 409);
  return c.json({ ...view(created), key: created.key }, 201);
}

export async function update(c: Context<App>) {
  const parsed = parse(await readBody(c));
  if (typeof parsed === "string") return c.json({ error: parsed }, 400);
  if (!Object.keys(parsed.settings).length) return c.json({ error: "send label or disabled" }, 400);
  const updated = await updateKey(c.env, c.get("session").id, c.req.param("id")!, parsed.settings);
  return updated ? c.json({ ok: true }) : c.json({ error: "no such key (it may have been revoked or regenerated)" }, 404);
}

export async function rotate(c: Context<App>) {
  const rotated = await rotateKey(c.env, c.get("session").id, c.req.param("id")!);
  if (!rotated) return c.json({ error: "no such key (it may have been revoked or regenerated already)" }, 404);
  return c.json({ ...view(rotated), key: rotated.key }, 201);
}

export async function revoke(c: Context<App>) {
  const revoked = await revokeOwnKey(c.env, c.get("session").id, c.req.param("id")!);
  return revoked ? c.json({ ok: true }) : c.json({ error: "no such key" }, 404);
}
