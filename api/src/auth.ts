import type { MiddlewareHandler } from "hono";
import { findSession } from "./access";
import { findKey, touchKey } from "./db";
import type { App, Env } from "./types";

export const bearer = (c: { req: { header: (n: string) => string | undefined } }) =>
  (c.req.header("Authorization") ?? "").replace(/^Bearer\s+/i, "");

// clients: an access key → the user and the engines it may use.
// Sent as `Authorization: Bearer <key>`, or as `X-API-Key: <key>` (the Clep plugin's header).
export const requireUser: MiddlewareHandler<App> = async (c, next) => {
  const auth = await findKey(c.env, bearer(c) || (c.req.header("X-API-Key") ?? "").trim());
  if (!auth) return c.json({ error: "unauthorized" }, 401);
  c.set("auth", auth);
  c.executionCtx.waitUntil(touchKey(c.env, auth.keyId).catch((e) => console.error("key last used:", e)));
  await next();
};

export const requireSession: MiddlewareHandler<App> = async (c, next) => {
  const user = await findSession(c.env, bearer(c));
  if (!user) return c.json({ error: "sign in again" }, 401);
  c.set("session", user);
  await next();
};

async function sameSecret(given: string, expected: string): Promise<boolean> {
  const digest = async (value: string) => crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  const [a, b] = await Promise.all([digest(given), digest(expected)]);
  return crypto.subtle.timingSafeEqual(a, b);
}

const fixed = (key: keyof Pick<Env, "ADMIN_KEY" | "INTERNAL_KEY">): MiddlewareHandler<App> => async (c, next) => {
  const expected = c.env[key];
  if (!expected || !(await sameSecret(bearer(c), expected))) return c.json({ error: "unauthorized" }, 401);
  await next();
};

export const requireAdmin = fixed("ADMIN_KEY");        // you
export const requireInternal = fixed("INTERNAL_KEY");  // the Google VM
