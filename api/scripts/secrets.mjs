// Pushes the Worker's secrets in one go: ADMIN_KEY + INTERNAL_KEY from api/.env, DATABASE_URL from ../.env.local (Neon).
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";

const read = (f) => existsSync(f) ? Object.fromEntries(readFileSync(f, "utf8").split("\n")
  .map((l) => l.match(/^([A-Z_]+)=(.*)$/)).filter(Boolean).map((m) => [m[1], m[2].replace(/^["']|["']$/g, "")])) : {};
const env = { ...read(".env"), ...read("../.env.local") };
const want = ["ADMIN_KEY", "INTERNAL_KEY", "DATABASE_URL"];
const missing = want.filter((k) => !env[k]);
if (missing.length) throw new Error(`missing: ${missing.join(", ")}`);
writeFileSync(".secrets.json", JSON.stringify(Object.fromEntries(want.map((k) => [k, env[k]]))));
try { execFileSync("npx", ["wrangler", "secret", "bulk", ".secrets.json"], { stdio: "inherit" }); }
finally { rmSync(".secrets.json", { force: true }); }
