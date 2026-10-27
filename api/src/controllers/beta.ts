import type { Context } from "hono";
import { isAdminEmail, normalizeEmail, reserveSeat, revokeSession, signIn } from "../access";
import { bearer } from "../auth";
import { newReservationEmail } from "../beta-emails";
import { sendEmail } from "../resend";
import type { App } from "../types";

type Reservation = { name?: unknown; email?: unknown; product_url?: unknown };
type Credentials = { email?: unknown; code?: unknown };

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const ACCESS_CODE = /^\d{6}$/;

function validProductUrl(value: unknown): string | null | false {
  if (value === undefined || value === null || value === "") return null;
  if (typeof value !== "string" || value.length > 500) return false;
  try {
    const url = new URL(value.trim());
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : false;
  } catch {
    return false;
  }
}

export async function reserve(c: Context<App>) {
  const body = await c.req.json<Reservation>().catch(() => ({} as Reservation));
  const name = typeof body.name === "string" ? body.name.trim() : "";
  const email = typeof body.email === "string" ? normalizeEmail(body.email) : "";
  const productUrl = validProductUrl(body.product_url);
  if (!name || name.length > 100) return c.json({ error: "name is required (up to 100 characters)" }, 400);
  if (!EMAIL.test(email) || email.length > 254) return c.json({ error: "a valid email is required" }, 400);
  if (productUrl === false) return c.json({ error: "product_url must be an http(s) address" }, 400);
  const created = await reserveSeat(c.env, name, email, productUrl);
  if (!created) return c.json({ status: "already_reserved" }, 200);
  c.executionCtx.waitUntil(sendEmail(c.env, newReservationEmail(c.env, created.id, name, email, productUrl))
    .then((result) => { if (!result.sent) console.error("admin notice:", result.error); }));
  return c.json({ status: "reserved", id: created.id }, 201);
}

export async function signin(c: Context<App>) {
  const body = await c.req.json<Credentials>().catch(() => ({} as Credentials));
  const email = typeof body.email === "string" ? normalizeEmail(body.email) : "";
  const code = typeof body.code === "string" ? body.code.trim() : "";
  if (!email || !ACCESS_CODE.test(code)) return c.json({ error: "email and the 6-digit access code are required" }, 400);
  const result = await signIn(c.env, email, code);
  if (result.ok) return c.json({ token: result.token, expires_at: result.expiresAt, user: result.user, is_admin: isAdminEmail(c.env, result.user.email) });
  return result.reason === "locked"
    ? c.json({ error: "too many wrong codes: try again in 15 minutes" }, 429)
    : c.json({ error: "wrong email or access code" }, 401);
}

export const session = (c: Context<App>) => c.json({ user: c.get("session"), is_admin: isAdminEmail(c.env, c.get("session").email) });

export async function signout(c: Context<App>) {
  await revokeSession(c.env, bearer(c));
  return c.json({ ok: true });
}
