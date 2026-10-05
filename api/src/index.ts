import { Hono } from "hono";
import { cors } from "hono/cors";
import { sweep } from "./db";
import { adminRoutes, internalRoutes, v1 } from "./routes";
import type { App, Env } from "./types";

const app = new Hono<App>();

// browsers (the Clep dashboard) call /v1 directly with the user's own access key
app.use("/v1/*", cors({ origin: "*", allowHeaders: ["Authorization", "Content-Type"], allowMethods: ["GET", "POST", "OPTIONS"] }));

app.get("/health", (c) => c.json({ ok: true }));
app.route("/v1", v1);
app.route("/admin", adminRoutes);
app.route("/internal", internalRoutes);

export default {
  fetch: app.fetch,
  // every minute: jobs still queued but no VM up (it was shutting down, or Spot reclaimed it) → start it
  async scheduled(_: ScheduledController, env: Env, ctx: ExecutionContext) {
    ctx.waitUntil(sweep(env));
  },
};
