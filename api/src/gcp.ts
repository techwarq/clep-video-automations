/**
 * Starts the render VM when there is work. Auth: a Google service account key (secret GCP_SA_KEY, JSON) →
 * self-signed RS256 JWT → OAuth access token, cached per isolate until a minute before expiry.
 * The service account only needs compute.instances.get + compute.instances.start on that one VM.
 */
import type { Env } from "./types";

let cached: { token: string; exp: number } | null = null;

const b64url = (data: ArrayBuffer | string) => {
  const bytes = typeof data === "string" ? new TextEncoder().encode(data) : new Uint8Array(data);
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
};

async function accessToken(env: Env): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  if (cached && cached.exp - 60 > now) return cached.token;
  const sa = JSON.parse(env.GCP_SA_KEY) as { client_email: string; private_key: string };
  const unsigned = `${b64url(JSON.stringify({ alg: "RS256", typ: "JWT" }))}.${b64url(JSON.stringify({
    iss: sa.client_email, scope: "https://www.googleapis.com/auth/compute",
    aud: "https://oauth2.googleapis.com/token", iat: now, exp: now + 3600,
  }))}`;
  const der = Uint8Array.from(atob(sa.private_key.replace(/-----[^-]+-----|\s+/g, "")), (c) => c.charCodeAt(0));
  const key = await crypto.subtle.importKey("pkcs8", der, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, new TextEncoder().encode(unsigned));
  const res = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer", assertion: `${unsigned}.${b64url(sig)}` }),
  });
  if (!res.ok) throw new Error(`google token exchange failed: HTTP ${res.status} ${await res.text()}`);
  const tok = (await res.json()) as { access_token: string; expires_in: number };
  cached = { token: tok.access_token, exp: now + tok.expires_in };
  return tok.access_token;
}

const vmUrl = (env: Env) =>
  `https://compute.googleapis.com/compute/v1/projects/${env.GCP_PROJECT}/zones/${env.GCP_ZONE}/instances/${env.GCP_VM}`;

export async function vmStatus(env: Env): Promise<string> {
  const res = await fetch(vmUrl(env), { headers: { Authorization: `Bearer ${await accessToken(env)}` } });
  if (!res.ok) throw new Error(`instances.get failed: HTTP ${res.status} ${await res.text()}`);
  return ((await res.json()) as { status: string }).status;   // RUNNING | STAGING | PROVISIONING | STOPPING | TERMINATED | …
}

/** Start the VM if it is stopped. Returns what it found / did. Safe to call often. */
export async function ensureVm(env: Env): Promise<string> {
  if (!env.GCP_SA_KEY) return "no GCP_SA_KEY: VM control disabled";
  const status = await vmStatus(env);
  if (status !== "TERMINATED" && status !== "STOPPED" && status !== "SUSPENDED") return status;  // up, or on its way up/down
  const res = await fetch(`${vmUrl(env)}/${status === "SUSPENDED" ? "resume" : "start"}`, {
    method: "POST", headers: { Authorization: `Bearer ${await accessToken(env)}` },
  });
  if (!res.ok) throw new Error(`instances.start failed: HTTP ${res.status} ${await res.text()}`);
  return `${status} → starting`;
}
