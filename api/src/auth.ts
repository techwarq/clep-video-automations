import type { MiddlewareHandler } from "hono";
import { findSession, isAdminEmail } from "./access";
import { findKey, touchKey } from "./keys";
import type { App, Env } from "./types";

export const bearer = (c: { req: { header: (n: string) => string | undefined } }) =>
  (c.req.header("Authorization") ?? "").replace(/^Bearer\s+/i, "");

// clients: an access key → the user and the engines it may use.
// Sent as `Authorization: Bearer <key>`, or as `X-API-Key: <key>` (the Clep plugin's header).
export const requireUser: MiddlewareHandler<App> = async (c, next) => {
  const found = await findKey(c.env, (bearer(c) || c.req.header("X-API-Key") || "").trim());
  if (!found) return c.json({ error: "unauthorized: this API key is invalid or was revoked" }, 401);
  if (found.disabled) return c.json({ error: "unauthorized: this API key is paused; resume it in the Clep dashboard (API Keys)" }, 401);
  if (found.expiredAt) return c.json({ error: `unauthorized: this API key expired on ${new Date(found.expiredAt).toISOString().slice(0, 10)}; regenerate it in the Clep dashboard (API Keys)` }, 401);
  const auth = found.auth;
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

export const requireAdminSession: MiddlewareHandler<App> = async (c, next) => {
  const user = await findSession(c.env, bearer(c));
  if (!user) return c.json({ error: "sign in again" }, 401);
  if (!isAdminEmail(c.env, user.email)) return c.json({ error: "only Clep admins can open this" }, 403);
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
