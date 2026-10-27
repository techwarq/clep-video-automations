import type { Context } from "hono";
import { issueKey, listKeys, revokeOwnKey, rotateKey, updateKey, type KeySettings } from "../keys";
import { limitsOf } from "../plans";
import type { App, Plan } from "../types";
import { monthlyUsage } from "../usage";

const MAX_LABEL = 60;
const MAX_MINUTE_LIMIT = 100_000;
const DEFAULT_LABEL = "Untitled key";

type KeyBody = { label?: unknown; minute_limit?: unknown; disabled?: unknown };

function settingsFrom(body: KeyBody): KeySettings | string {
  const settings: KeySettings = {};
  if (body.label !== undefined) {
    if (typeof body.label !== "string" || body.label.trim().length > MAX_LABEL) return `label must be text up to ${MAX_LABEL} characters`;
    settings.label = body.label.trim() || DEFAULT_LABEL;
  }
  if (body.minute_limit !== undefined) {
    const limit = body.minute_limit;
    const valid = limit === null || (Number.isInteger(limit) && (limit as number) >= 1 && (limit as number) <= MAX_MINUTE_LIMIT);
    if (!valid) return `minute_limit must be a whole number of minutes from 1 to ${MAX_MINUTE_LIMIT}, or null for the plan's limit`;
    settings.minuteLimit = limit as number | null;
  }
  if (body.disabled !== undefined) {
    if (typeof body.disabled !== "boolean") return "disabled must be true or false";
    settings.disabled = body.disabled;
  }
  return settings;
}

const readBody = (c: Context<App>) => c.req.json<KeyBody>().catch(() => ({} as KeyBody));

const view = (row: Record<string, unknown>) => ({
  id: row.id, label: row.label, prefix: row.prefix, last4: row.last4, minute_limit: row.minute_limit,
  disabled: row.disabled_at !== null, used_seconds: Number(row.used_seconds ?? 0),
  created_at: row.created_at, last_used_at: row.last_used_at,
});

export async function list(c: Context<App>) {
  const user = c.get("session");
  const [keys, usage] = await Promise.all([listKeys(c.env, user.id), monthlyUsage(c.env, user.id)]);
  const limits = limitsOf(usage.plan);
  return c.json({
    keys: keys.map(view),
    plan: { name: usage.plan, keys: limits.keys, requests_per_minute: limits.requestsPerMinute, active_jobs: limits.activeJobs, export_minutes: limits.exportMinutes },
  });
}

export async function create(c: Context<App>) {
  const user = c.get("session");
  const settings = settingsFrom(await readBody(c));
  if (typeof settings === "string") return c.json({ error: settings }, 400);
  const plan = (await monthlyUsage(c.env, user.id)).plan as Plan;
  const cap = limitsOf(plan).keys;
  const created = await issueKey(c.env, user.id, ["clep"], settings.label ?? DEFAULT_LABEL, settings.minuteLimit ?? null, cap);
  if (!created) return c.json({ error: `your ${plan} plan allows ${cap} active keys: revoke one first` }, 409);
  return c.json({ ...view(created), key: created.key }, 201);
}

export async function update(c: Context<App>) {
  const settings = settingsFrom(await readBody(c));
  if (typeof settings === "string") return c.json({ error: settings }, 400);
  if (!Object.keys(settings).length) return c.json({ error: "send label, minute_limit or disabled" }, 400);
  const updated = await updateKey(c.env, c.get("session").id, c.req.param("id")!, settings);
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
