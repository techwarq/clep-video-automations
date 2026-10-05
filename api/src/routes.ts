import { Hono } from "hono";
import { requireAdmin, requireInternal, requireUser } from "./auth";
import * as admin from "./controllers/admin";
import * as engines from "./controllers/engines";
import * as internal from "./controllers/internal";
import * as jobs from "./controllers/jobs";
import * as videos from "./controllers/videos";
import type { App } from "./types";

// clients, with an access key
export const v1 = new Hono<App>()
  .use(requireUser)
  .post("/reels", engines.create("reels"))
  .post("/motion", engines.create("motion"))
  .get("/jobs", jobs.list)
  .get("/jobs/:id", jobs.get)
  .post("/jobs/:id/retry", jobs.retry)
  .get("/videos", videos.list)
  .get("/videos/:id", videos.download);

// you: users and their access keys
export const adminRoutes = new Hono<App>()
  .use(requireAdmin)
  .post("/users", admin.addUser)
  .post("/users/:id/keys", admin.addKey)
  .delete("/keys/:id", admin.dropKey)
  .get("/vm", admin.vm)
  .post("/vm/start", admin.vmStart);

// the Google VM
export const internalRoutes = new Hono<App>()
  .use(requireInternal)
  .patch("/jobs/:id", internal.update)
  .put("/jobs/:id/video", internal.putVideo)
  .put("/jobs/:id/draft", internal.putDraft)
  .get("/drafts/*", internal.getDraftFile);
