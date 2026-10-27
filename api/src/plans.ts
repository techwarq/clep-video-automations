import type { Plan } from "./types";

export type PlanLimits = { exportMinutes: number; requestsPerMinute: number; activeJobs: number; keys: number };

export const PLAN_LIMITS: Record<Plan, PlanLimits> = {
  free: { exportMinutes: 3, requestsPerMinute: 30, activeJobs: 1, keys: 3 },
  beta: { exportMinutes: 10, requestsPerMinute: 60, activeJobs: 3, keys: 10 },
  pro: { exportMinutes: 30, requestsPerMinute: 120, activeJobs: 5, keys: 25 },
  studio: { exportMinutes: 60, requestsPerMinute: 300, activeJobs: 10, keys: 50 },
};

export const RATE_LIMITERS = {
  free: "KEY_RATE_FREE",
  beta: "KEY_RATE_BETA",
  pro: "KEY_RATE_PRO",
  studio: "KEY_RATE_STUDIO",
} as const satisfies Record<Plan, string>;

export const limitsOf = (plan: Plan | null | undefined) => PLAN_LIMITS[plan ?? "free"] ?? PLAN_LIMITS.free;
