import { db, isUuid, randomToken, sha256 } from "./db";
import type { Auth, Engine, Env, Plan } from "./types";

const KEY_PREFIX = "clep_sk_";
const SHOWN_PREFIX = 12;
export const EXPIRY_DAYS = [7, 30, 60, 90, 365];

export type KeyLookup = { auth: Auth; disabled: boolean; expiredAt: string | Date | null };
export type KeySettings = { label?: string; disabled?: boolean };

const KEY_COLUMNS = "id, label, prefix, last4, engines, disabled_at, expires_at, created_at, last_used_at";
const STILL_ACTIVE = "revoked_at IS NULL AND (expires_at IS NULL OR expires_at > now())";

async function newSecret() {
  const key = randomToken(KEY_PREFIX);
  return { key, hash: await sha256(key), prefix: key.slice(0, SHOWN_PREFIX), last4: key.slice(-4) };
}

export async function findKey(env: Env, key: string): Promise<KeyLookup | null> {
  if (!key) return null;
  const [row] = await db(env)`
    SELECT k.id, k.user_id, k.engines, k.disabled_at, k.expires_at, (k.expires_at IS NOT NULL AND k.expires_at <= now()) AS expired, u.plan
    FROM access_keys k JOIN users u ON u.id = k.user_id
    WHERE k.key_hash = ${await sha256(key)} AND k.revoked_at IS NULL`;
  if (!row) return null;
  const auth: Auth = { userId: row.user_id, keyId: row.id, engines: row.engines, plan: row.plan as Plan };
  return { auth, disabled: row.disabled_at !== null, expiredAt: row.expired ? row.expires_at : null };
}

export const touchKey = (env: Env, keyId: string) =>
  db(env)`UPDATE access_keys SET last_used_at = now()
          WHERE id = ${keyId} AND (last_used_at IS NULL OR last_used_at < now() - interval '5 minutes')`;

export async function issueKey(env: Env, userId: string, engines: Engine[], label: string, expiresInDays: number | null, cap: number) {
  const sql = db(env);
  const secret = await newSecret();
  const [, created] = await sql.transaction([
    sql`SELECT id FROM users WHERE id = ${userId} FOR UPDATE`,
    sql.query(
      `INSERT INTO access_keys (user_id, key_hash, prefix, last4, label, engines, expires_at)
       SELECT $1, $2, $3, $4, $5, $6, CASE WHEN $7::int IS NULL THEN NULL ELSE now() + make_interval(days => $7::int) END
       WHERE (SELECT count(*) FROM access_keys WHERE user_id = $1 AND ${STILL_ACTIVE}) < $8
       RETURNING ${KEY_COLUMNS}`,
      [userId, secret.hash, secret.prefix, secret.last4, label, engines, expiresInDays, cap],
    ),
  ]);
  return created[0] ? { ...created[0], key: secret.key } : null;
}

export async function rotateKey(env: Env, userId: string, keyId: string) {
  if (!isUuid(keyId)) return null;
  const sql = db(env);
  const secret = await newSecret();
  const [, created] = await sql.transaction([
    sql`SELECT id FROM users WHERE id = ${userId} FOR UPDATE`,
    sql.query(
      `INSERT INTO access_keys (user_id, key_hash, prefix, last4, label, engines, expires_at)
       SELECT user_id, $3, $4, $5, label, engines, CASE WHEN expires_at IS NULL THEN NULL ELSE now() + (expires_at - created_at) END
       FROM access_keys WHERE id = $1 AND user_id = $2 AND revoked_at IS NULL
       RETURNING ${KEY_COLUMNS}`,
      [keyId, userId, secret.hash, secret.prefix, secret.last4],
    ),
    sql`UPDATE access_keys SET revoked_at = now(), replaced_by = (SELECT id FROM access_keys WHERE key_hash = ${secret.hash})
        WHERE id = ${keyId} AND user_id = ${userId} AND revoked_at IS NULL`,
  ]);
  return created[0] ? { ...created[0], key: secret.key } : null;
}

export const listKeys = (env: Env, userId: string) =>
  db(env)`
    SELECT k.id, k.label, k.prefix, k.last4, k.engines, k.disabled_at, k.expires_at, k.created_at, k.last_used_at,
      COALESCE((SELECT sum(l.seconds) FROM usage_ledger l JOIN jobs j ON j.id = l.job_id
                WHERE j.key_id = k.id AND l.kind = 'export' AND l.created_at >= date_trunc('month', now())), 0)::float AS used_seconds
    FROM access_keys k WHERE k.user_id = ${userId} AND k.revoked_at IS NULL ORDER BY k.created_at DESC`;

export async function updateKey(env: Env, userId: string, keyId: string, settings: KeySettings) {
  if (!isUuid(keyId)) return null;
  const hasLabel = settings.label !== undefined;
  const hasDisabled = settings.disabled !== undefined;
  const [row] = await db(env)`
    UPDATE access_keys SET
      label = CASE WHEN ${hasLabel} THEN ${settings.label ?? null} ELSE label END,
      disabled_at = CASE WHEN NOT ${hasDisabled} THEN disabled_at WHEN ${settings.disabled ?? false} THEN COALESCE(disabled_at, now()) ELSE NULL END
    WHERE id = ${keyId} AND user_id = ${userId} AND revoked_at IS NULL
    RETURNING id`;
  return row ?? null;
}

export const revokeOwnKey = async (env: Env, userId: string, keyId: string) =>
  isUuid(keyId) && (await db(env)`UPDATE access_keys SET revoked_at = now()
                                  WHERE id = ${keyId} AND user_id = ${userId} AND revoked_at IS NULL RETURNING id`).length > 0;

export const revokeKey = async (env: Env, keyId: string) =>
  isUuid(keyId) && db(env)`UPDATE access_keys SET revoked_at = now() WHERE id = ${keyId}`;
