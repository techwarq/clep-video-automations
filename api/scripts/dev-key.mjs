// Local dev: an access key for the dashboard and the Clep plugin against `wrangler dev` (http://127.0.0.1:8787).
//   node scripts/dev-key.mjs you@example.com                → prints a key for every engine
//   node scripts/dev-key.mjs you@example.com clep           → only the engines listed
// Reads ADMIN_KEY + DATABASE_URL from api/.dev.vars (the Neon dev branch) — never production.
import { neon } from "@neondatabase/serverless";
import { readFileSync } from "node:fs";
import { useLocalDatabaseWhenAsked } from "../src/local-database.ts";

const vars = Object.fromEntries(readFileSync(new URL("../.dev.vars", import.meta.url), "utf8").split("\n")
  .map((l) => l.match(/^([A-Z_]+)=(.*)$/)).filter(Boolean).map((m) => [m[1], m[2].replace(/^["']|["']$/g, "")]));
const [email, ...listed] = process.argv.slice(2);
if (!email) throw new Error("usage: node scripts/dev-key.mjs <email> [engine …]");
const engines = listed.length ? listed : ["reels", "motion", "clep"];
const base = process.env.API ?? "http://127.0.0.1:8787";
const admin = (path, body) => fetch(base + path, {
  method: "POST", headers: { Authorization: `Bearer ${vars.ADMIN_KEY}`, "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

let r = await admin("/admin/users", { email, name: email.split("@")[0] });
let userId;
if (r.status === 201) userId = (await r.json()).id;
else if (r.status === 409) {
  useLocalDatabaseWhenAsked(vars.DATABASE_URL);
  userId = (await neon(vars.DATABASE_URL)`SELECT id FROM users WHERE email = ${email}`)[0].id;
} else throw new Error(`creating the user failed: HTTP ${r.status} ${await r.text()} (is wrangler dev running?)`);

r = await admin(`/admin/users/${userId}/keys`, { engines, label: "local dev" });
if (r.status !== 201) throw new Error(`creating the key failed: HTTP ${r.status} ${await r.text()}`);
console.log((await r.json()).key);
