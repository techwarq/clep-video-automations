import { readFileSync } from "node:fs";

const vars = Object.fromEntries(readFileSync(new URL("../.dev.vars", import.meta.url), "utf8").split("\n")
  .map((line) => line.match(/^([A-Z_]+)=(.*)$/)).filter(Boolean).map((m) => [m[1], m[2].replace(/^["']|["']$/g, "")]));
const args = process.argv.slice(2);
const replaceCode = args.includes("--new-code");
const [email, name = email?.split("@")[0]] = args.filter((arg) => arg !== "--new-code");
if (!email) throw new Error("usage: node scripts/dev-signin.mjs <email> [name] [--new-code]");
const base = process.env.API ?? "http://127.0.0.1:8799";
const call = async (path, init = {}) => {
  const response = await fetch(base + path, { ...init, headers: { "Content-Type": "application/json", ...init.headers } });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status} ${await response.text()} (is the local API running?)`);
  return response.json();
};
const admin = { Authorization: `Bearer ${vars.ADMIN_KEY}` };

await call("/api/reserve", { method: "POST", body: JSON.stringify({ name, email }) });
const { requests } = await call("/admin/beta-requests", { headers: admin });
const request = requests.find((r) => r.email === email.trim().toLowerCase());
if (request.status === "approved" && !replaceCode) {
  console.log(`${email} is already approved: the code you were given still works. Run again with --new-code to replace it (the old one stops working).`);
  process.exit(0);
}
const { access_code } = await call(`/admin/beta-requests/${request.id}/approve`, { method: "POST", headers: admin });
console.log(`Sign in at http://localhost:3000/signin?email=${encodeURIComponent(email)} with code ${access_code}`);
