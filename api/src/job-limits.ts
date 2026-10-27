import type { Context } from "hono";
import { db } from "./db";
import type { App } from "./types";
import { hasMinutesLeft, monthlyUsage } from "./usage";

export const MAX_ACTIVE_JOBS = 3;

const activeJobCount = async (c: Context<App>, userId: string) => {
  const [row] = await db(c.env)`SELECT count(*)::int AS active FROM jobs WHERE user_id = ${userId} AND status IN ('queued', 'running')`;
  return Number(row?.active ?? 0);
};

export async function outOfMinutes(c: Context<App>, userId: string) {
  const usage = await monthlyUsage(c.env, userId);
  if (hasMinutesLeft(usage)) return null;
  return c.json({ error: `all ${usage.limit_seconds / 60} export minutes of the ${usage.plan} plan are used this month`, usage }, 402);
}

export async function tooManyActiveJobs(c: Context<App>, userId: string) {
  if ((await activeJobCount(c, userId)) < MAX_ACTIVE_JOBS) return null;
  return c.json({ error: `you already have ${MAX_ACTIVE_JOBS} videos queued or rendering: wait for one to finish` }, 429);
}

export async function refuseNewJob(c: Context<App>, userId: string, metered: boolean) {
  return (await tooManyActiveJobs(c, userId)) ?? (metered ? await outOfMinutes(c, userId) : null);
}
