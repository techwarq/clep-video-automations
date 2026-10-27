import type { MiddlewareHandler } from "hono";
import { limitsOf, RATE_LIMITERS } from "./plans";
import type { App, Env } from "./types";

type Limiter = keyof Pick<Env, "SIGNIN_LIMITER" | "RESERVE_LIMITER">;

export const limitPerVisitor = (limiter: Limiter): MiddlewareHandler<App> => async (c, next) => {
  const visitor = c.req.header("CF-Connecting-IP") ?? "unknown";
  const { success } = await c.env[limiter].limit({ key: `${c.req.path}:${visitor}` });
  if (!success) return c.json({ error: "too many attempts: wait a minute and try again" }, 429);
  await next();
};

export const limitPerKey: MiddlewareHandler<App> = async (c, next) => {
  const { keyId, plan } = c.get("auth");
  const perMinute = limitsOf(plan).requestsPerMinute;
  const { success } = await c.env[RATE_LIMITERS[plan] ?? RATE_LIMITERS.free].limit({ key: keyId });
  if (!success) {
    c.header("Retry-After", "60");
    return c.json({ error: `rate limit: your ${plan} plan allows ${perMinute} requests a minute per key; retry in a minute` }, 429);
  }
  c.header("X-RateLimit-Limit", String(perMinute));
  await next();
};
