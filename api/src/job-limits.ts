import type { Context } from "hono";
import { db } from "./db";
import { keyUsedSeconds } from "./keys";
import { limitsOf } from "./plans";
import type { App, Owner, Plan } from "./types";
import { hasMinutesLeft, monthlyUsage } from "./usage";

export async function outOfMinutes(c: Context<App>, userId: string) {
  const usage = await monthlyUsage(c.env, userId);
  if (hasMinutesLeft(usage)) return null;
  return c.json({ error: `all ${usage.limit_seconds / 60} export minutes of the ${usage.plan} plan are used this month`, usage }, 402);
}

export async function tooManyActiveJobs(c: Context<App>, userId: string) {
  const [row] = await db(c.env)`
    SELECT users.plan, (SELECT count(*)::int FROM jobs WHERE user_id = users.id AND status IN ('queued', 'running')) AS active
    FROM users WHERE id = ${userId}`;
  const allowed = limitsOf(row?.plan as Plan).activeJobs;
  if (Number(row?.active ?? 0) < allowed) return null;
  return c.json({ error: `your ${row?.plan ?? "free"} plan runs ${allowed} video${allowed === 1 ? "" : "s"} at a time: wait for one to finish` }, 429);
}

async function keyOutOfMinutes(c: Context<App>, owner: Owner) {
  const limit = owner.keyId && c.get("auth")?.keyId === owner.keyId ? c.get("auth").minuteLimit : null;
  if (!owner.keyId || !limit) return null;
  if ((await keyUsedSeconds(c.env, owner.keyId)) < limit * 60) return null;
  return c.json({ error: `this API key's limit of ${limit} export minute${limit === 1 ? "" : "s"} this month is used: raise it in the Clep dashboard (API Keys)` }, 402);
}

export async function refuseNewJob(c: Context<App>, owner: Owner, metered: boolean) {
  return (await tooManyActiveJobs(c, owner.userId)) ?? (metered ? (await keyOutOfMinutes(c, owner)) ?? (await outOfMinutes(c, owner.userId)) : null);
}
