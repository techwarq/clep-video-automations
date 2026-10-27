import type { Env } from "./types";

export type Email = { to: string; subject: string; html: string; text: string };
export type EmailResult = { sent: true; id: string } | { sent: false; error: string };

export async function sendEmail(env: Env, email: Email): Promise<EmailResult> {
  if (!env.RESEND_API_KEY) return { sent: false, error: "RESEND_API_KEY is not set" };
  const response = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${env.RESEND_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({ from: env.EMAIL_FROM, reply_to: env.ADMIN_EMAIL, ...email }),
  });
  const body = (await response.json().catch(() => ({}))) as { id?: string; message?: string };
  return response.ok && body.id
    ? { sent: true, id: body.id }
    : { sent: false, error: `resend ${response.status}: ${body.message ?? "no details"}` };
}
