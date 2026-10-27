import { Hono } from "hono";
import { secureHeaders } from "hono/secure-headers";
import { browserCors } from "./browser-access";
import { sweep } from "./db";
import { recorderFile } from "./recorder";
import { adminPanel, adminRoutes, betaAccess, clepApi, internalRoutes, platform, v1 } from "./routes";
import skill from "./skill.md";
import type { App, Env } from "./types";

const app = new Hono<App>();
const SKILL_BASE_URL = "https://api.clep.abstraklabs.com";

const BROWSER_PATHS = ["/v1/*", "/api/reserve", "/api/signin", "/api/session", "/api/signout", "/api/me", "/api/me/*", "/api/admin/*"];

app.use("*", secureHeaders());
for (const path of BROWSER_PATHS) app.use(path, browserCors);

app.get("/health", (c) => c.json({ ok: true }));

app.get("/skill.md", (c) => c.body(skill.replaceAll(SKILL_BASE_URL, c.env.API_URL), 200, { "Content-Type": "text/markdown; charset=utf-8", "Cache-Control": "public, max-age=300" }));
app.get("/recorder/:file", recorderFile);
app.route("/v1", v1);
app.route("/api", betaAccess);
app.route("/api/me", platform);
app.route("/api/admin", adminPanel);
app.route("/api", clepApi);
app.route("/admin", adminRoutes);
app.route("/internal", internalRoutes);

export default {
  fetch: app.fetch,
  // every minute: jobs still queued but no VM up (it was shutting down, or Spot reclaimed it) → start it
  async scheduled(controller: ScheduledController, env: Env, ctx: ExecutionContext) {
    ctx.waitUntil(sweep(env, controller.scheduledTime));
  },
};
