// Applies migrations/*.sql in order, once each, recorded in schema_migrations.
//   DATABASE_URL=… node scripts/migrate.mjs      (npm run migrate reads ../.env.local)
import { neon } from "@neondatabase/serverless";
import { readdirSync, readFileSync } from "node:fs";

const url = process.env.DATABASE_URL_UNPOOLED || process.env.DATABASE_URL;
if (!url) throw new Error("DATABASE_URL is not set");
const sql = neon(url);
const dir = new URL("../migrations/", import.meta.url);

await sql`CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())`;
const done = new Set((await sql`SELECT name FROM schema_migrations`).map((r) => r.name));
for (const name of readdirSync(dir).filter((f) => f.endsWith(".sql")).sort()) {
  if (done.has(name)) continue;
  const statements = readFileSync(new URL(name, dir), "utf8")
    .split(/;\s*$/m).map((s) => s.replace(/^\s*--.*$/gm, "").trim()).filter(Boolean);
  await sql.transaction([...statements.map((s) => sql.query(s)), sql`INSERT INTO schema_migrations (name) VALUES (${name})`]);
  console.log(`applied ${name} (${statements.length} statements)`);
}
console.log("migrations up to date");
