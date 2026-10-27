import { db } from "./db";
import type { Env, Plan } from "./types";

export const PLAN_EXPORT_MINUTES: Record<Plan, number> = { free: 3, beta: 10, pro: 30, studio: 60 };

export type Usage = { plan: Plan; used_seconds: number; limit_seconds: number; period_start: string };

export async function monthlyUsage(env: Env, userId: string): Promise<Usage> {
  const [row] = await db(env)`
    SELECT users.plan, date_trunc('month', now()) AS period_start,
      COALESCE((SELECT sum(CASE WHEN kind = 'export' THEN seconds WHEN kind IN ('refund', 'grant') THEN -seconds END)
                FROM usage_ledger WHERE user_id = users.id AND created_at >= date_trunc('month', now())), 0) AS used
    FROM users WHERE id = ${userId}`;
  const plan = (row?.plan ?? "free") as Plan;
  return {
    plan,
    used_seconds: Math.max(Number(row?.used ?? 0), 0),
    limit_seconds: PLAN_EXPORT_MINUTES[plan] * 60,
    period_start: row?.period_start,
  };
}

export const hasMinutesLeft = (usage: Usage) => usage.used_seconds < usage.limit_seconds;

export const recordExport = (env: Env, jobId: string, seconds: number) =>
  db(env)`
    INSERT INTO usage_ledger (user_id, job_id, kind, seconds)
    SELECT user_id, id, 'export', ${seconds} FROM jobs WHERE id = ${jobId} AND engine = 'clep'
    ON CONFLICT (job_id) WHERE kind = 'export' DO NOTHING`;
