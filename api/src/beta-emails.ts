import type { Email } from "./resend";
import type { BetaRequest, Env } from "./types";

const escapeHtml = (value: string) =>
  value.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

const layout = (content: string) => `
<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;color:#15171c">
  <div style="font-weight:800;font-size:20px;margin-bottom:24px">Clep</div>
  ${content}
  <p style="color:#8b909b;font-size:12px;margin-top:32px">Clep · Your agent records it, Clep cuts it.</p>
</div>`;

export function accessCodeEmail(env: Env, request: BetaRequest, accessCode: string): Email {
  const signInUrl = `${env.PLATFORM_URL}/signin?email=${encodeURIComponent(request.email)}`;
  return {
    to: request.email,
    subject: `Your Clep beta access code: ${accessCode}`,
    text: [
      `Hi ${request.name},`,
      "",
      "You're in. Welcome to the Clep private beta.",
      "",
      `Your access code: ${accessCode}`,
      "",
      `Sign in with this email and the code at ${signInUrl}`,
      "",
      "Keep the code to yourself: it is how you sign in.",
    ].join("\n"),
    html: layout(`
      <p>Hi ${escapeHtml(request.name)},</p>
      <p>You're in. Welcome to the Clep private beta.</p>
      <p style="margin:24px 0 8px;color:#5d6370">Your access code</p>
      <div style="font-size:32px;font-weight:800;letter-spacing:8px;background:#f5f6f8;border-radius:10px;padding:16px;text-align:center">${accessCode}</div>
      <p style="margin-top:24px"><a href="${signInUrl}" style="background:#15171c;color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:600">Sign in to Clep</a></p>
      <p style="color:#5d6370;font-size:13px">Sign in with this email address and the code. Keep the code to yourself: it is how you sign in.</p>`),
  };
}

export function newReservationEmail(env: Env, id: string, name: string, email: string, productUrl: string | null): Email {
  const product = productUrl ?? "not given";
  return {
    to: env.ADMIN_EMAIL,
    subject: `New Clep beta request: ${name}`,
    text: `${name} <${email}> reserved a seat.\nProduct: ${product}\n\nApprove: POST /admin/beta-requests/${id}/approve`,
    html: layout(`
      <p><b>${escapeHtml(name)}</b> &lt;${escapeHtml(email)}&gt; reserved a seat.</p>
      <p>Product: ${escapeHtml(product)}</p>
      <p style="color:#5d6370;font-size:13px">Approve it with <code>POST /admin/beta-requests/${id}/approve</code>.</p>`),
  };
}
