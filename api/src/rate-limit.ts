import type { MiddlewareHandler } from "hono";
import type { App, Env } from "./types";

type Limiter = keyof Pick<Env, "SIGNIN_LIMITER" | "RESERVE_LIMITER">;

export const limitPerVisitor = (limiter: Limiter): MiddlewareHandler<App> => async (c, next) => {
  const visitor = c.req.header("CF-Connecting-IP") ?? "unknown";
  const { success } = await c.env[limiter].limit({ key: `${c.req.path}:${visitor}` });
  if (!success) return c.json({ error: "too many attempts: wait a minute and try again" }, 429);
  await next();
};
