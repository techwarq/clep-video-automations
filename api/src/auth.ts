import type { MiddlewareHandler } from "hono";
import { findKey } from "./db";
import type { App, Env } from "./types";

const bearer = (c: { req: { header: (n: string) => string | undefined } }) =>
  (c.req.header("Authorization") ?? "").replace(/^Bearer\s+/i, "");

// clients: an access key → the user and the engines it may use
export const requireUser: MiddlewareHandler<App> = async (c, next) => {
  const auth = await findKey(c.env, bearer(c));
  if (!auth) return c.json({ error: "unauthorized" }, 401);
  c.set("auth", auth);
  await next();
};

const fixed = (key: keyof Pick<Env, "ADMIN_KEY" | "INTERNAL_KEY">): MiddlewareHandler<App> => async (c, next) => {
  if (!c.env[key] || bearer(c) !== c.env[key]) return c.json({ error: "unauthorized" }, 401);
  await next();
};

export const requireAdmin = fixed("ADMIN_KEY");        // you
export const requireInternal = fixed("INTERNAL_KEY");  // the Google VM
