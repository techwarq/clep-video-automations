import { db, isUuid, randomToken, sha256 } from "./db";
import type { BetaRequest, Env, SessionUser } from "./types";

const MAX_FAILED_SIGNINS = 5;
const LOCK_MINUTES = 15;
const SESSION_DAYS = 30;
const CODE_SPACE = 1_000_000;

const codeHash = (email: string, code: string) => sha256(`${email}:${code}`);

export const normalizeEmail = (email: string) => email.trim().toLowerCase();

export function sixDigitCode(): string {
  const limit = Math.floor(0x1_0000_0000 / CODE_SPACE) * CODE_SPACE;
  const value = new Uint32Array(1);
  do crypto.getRandomValues(value); while (value[0] >= limit);
  return String(value[0] % CODE_SPACE).padStart(6, "0");
}

export async function reserveSeat(env: Env, name: string, email: string, productUrl: string | null) {
  const [created] = await db(env)`
    INSERT INTO beta_requests (name, email, product_url) VALUES (${name}, ${email}, ${productUrl})
    ON CONFLICT (email) DO NOTHING RETURNING id, status, created_at`;
  return created ?? null;
}

export const listBetaRequests = async (env: Env, status: string | undefined) =>
  (status
    ? await db(env)`SELECT * FROM beta_requests WHERE status = ${status} ORDER BY created_at`
    : await db(env)`SELECT * FROM beta_requests ORDER BY created_at`) as BetaRequest[];

export async function approveBetaRequest(env: Env, requestId: string) {
  if (!isUuid(requestId)) return null;
  const [request] = (await db(env)`SELECT * FROM beta_requests WHERE id = ${requestId}`) as BetaRequest[];
  if (!request) return null;
  const code = sixDigitCode();
  const [user] = await db(env)`
    INSERT INTO users (email, name) VALUES (${request.email}, ${request.name})
    ON CONFLICT (email) DO UPDATE SET name = COALESCE(users.name, excluded.name) RETURNING id`;
  const [approved] = (await db(env)`
    UPDATE beta_requests SET status = 'approved', user_id = ${user.id}, access_code_hash = ${await codeHash(request.email, code)},
      failed_signins = 0, locked_until = NULL, approved_at = now()
    WHERE id = ${requestId} RETURNING *`) as BetaRequest[];
  return { request: approved, accessCode: code };
}

export type SignInResult =
  | { ok: true; token: string; expiresAt: string; user: SessionUser }
  | { ok: false; reason: "invalid" | "locked" };

export async function signIn(env: Env, email: string, code: string): Promise<SignInResult> {
  const [request] = (await db(env)`
    SELECT * FROM beta_requests WHERE email = ${email} AND status = 'approved'`) as BetaRequest[];
  if (!request?.user_id || !request.access_code_hash) return { ok: false, reason: "invalid" };
  if (request.locked_until && new Date(request.locked_until) > new Date()) return { ok: false, reason: "locked" };
  if ((await codeHash(email, code)) !== request.access_code_hash) {
    await db(env)`
      UPDATE beta_requests SET
        failed_signins = CASE WHEN failed_signins + 1 >= ${MAX_FAILED_SIGNINS} THEN 0 ELSE failed_signins + 1 END,
        locked_until = CASE WHEN failed_signins + 1 >= ${MAX_FAILED_SIGNINS}
                            THEN now() + ${`${LOCK_MINUTES} minutes`}::interval ELSE locked_until END
      WHERE id = ${request.id}`;
    return { ok: false, reason: "invalid" };
  }
  await db(env)`UPDATE beta_requests SET failed_signins = 0, locked_until = NULL WHERE id = ${request.id}`;
  const token = randomToken("cs_");
  const [session] = await db(env)`
    INSERT INTO sessions (user_id, token_hash, expires_at)
    VALUES (${request.user_id}, ${await sha256(token)}, now() + ${`${SESSION_DAYS} days`}::interval)
    RETURNING expires_at`;
  return { ok: true, token, expiresAt: session.expires_at, user: { id: request.user_id, email: request.email, name: request.name } };
}

export async function findSession(env: Env, token: string): Promise<SessionUser | null> {
  if (!token) return null;
  const [row] = await db(env)`
    SELECT users.id, users.email, users.name FROM sessions JOIN users ON users.id = sessions.user_id
    WHERE sessions.token_hash = ${await sha256(token)} AND sessions.revoked_at IS NULL AND sessions.expires_at > now()`;
  return (row as SessionUser) ?? null;
}

export const revokeSession = async (env: Env, token: string) =>
  db(env)`UPDATE sessions SET revoked_at = now() WHERE token_hash = ${await sha256(token)} AND revoked_at IS NULL`;

export const isAdminEmail = (env: Env, email: string) =>
  (env.ADMIN_EMAILS ?? "").split(",").map((entry) => normalizeEmail(entry)).filter(Boolean).includes(normalizeEmail(email));

export const listMembers = (env: Env) =>
  db(env)`
    SELECT u.id, u.email, u.name, u.plan, u.created_at,
      (SELECT count(*)::int FROM access_keys k WHERE k.user_id = u.id AND k.revoked_at IS NULL) AS keys,
      (SELECT count(*)::int FROM jobs j WHERE j.user_id = u.id AND NOT (j.input ? 'scan')) AS clips,
      COALESCE((SELECT sum(l.seconds) FROM usage_ledger l WHERE l.user_id = u.id AND l.kind = 'export'
                AND l.created_at >= date_trunc('month', now())), 0)::float AS used_seconds,
      (SELECT max(k.last_used_at) FROM access_keys k WHERE k.user_id = u.id) AS last_active_at
    FROM users u ORDER BY u.created_at DESC LIMIT 500`;

export const setPlan = async (env: Env, userId: string, plan: string) =>
  isUuid(userId) && (await db(env)`UPDATE users SET plan = ${plan} WHERE id = ${userId} RETURNING id`).length > 0;
