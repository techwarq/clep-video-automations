import { Hono } from "hono";
import { requireAdmin, requireInternal, requireSession, requireUser } from "./auth";
import * as admin from "./controllers/admin";
import * as account from "./controllers/account";
import * as beta from "./controllers/beta";
import * as captures from "./controllers/captures";
import * as clep from "./controllers/clep";
import * as engines from "./controllers/engines";
import * as internal from "./controllers/internal";
import * as jobs from "./controllers/jobs";
import * as keys from "./controllers/keys";
import * as projects from "./controllers/projects";
import * as videos from "./controllers/videos";
import { limitPerKey, limitPerVisitor } from "./rate-limit";
import type { App } from "./types";

// clients, with an access key
export const v1 = new Hono<App>()
  .use(requireUser)
  .use(limitPerKey)
  // the key matched (requireUser) → who it belongs to and what it may make; the dashboard checks a key with this
  .get("/me", (c) => c.json({ user_id: c.get("auth").userId, engines: c.get("auth").engines }))
  .post("/reels", engines.create("reels"))
  .post("/motion", engines.create("motion"))
  .post("/clep", engines.create("clep"))
  .get("/jobs", jobs.list)
  .get("/jobs/:id", jobs.get)
  .post("/jobs/:id/retry", jobs.retry)
  .get("/projects", projects.list)
  .get("/videos", videos.list)
  .get("/videos/:id", videos.download);

// the Clep plugin (bin/clep): its own paths and shapes over the same jobs; key in X-API-Key or Authorization
export const clepApi = new Hono<App>()
  .get("/health", clep.health)
  .use(requireUser)
  .use(limitPerKey)
  .get("/features", clep.features)
  .post("/captures", captures.start)
  .put("/captures/:id/parts/:n", captures.part)
  .post("/captures/:id/complete", captures.complete)
  .post("/clips", clep.clip)
  .post("/projects/sync", projects.sync)
  .get("/jobs", clep.jobs)
  .get("/jobs/:id", clep.job)
  .get("/jobs/:id/video", clep.video);

export const betaAccess = new Hono<App>()
  .post("/reserve", limitPerVisitor("RESERVE_LIMITER"), beta.reserve)
  .post("/signin", limitPerVisitor("SIGNIN_LIMITER"), beta.signin)
  .get("/session", requireSession, beta.session)
  .post("/signout", requireSession, beta.signout);

export const platform = new Hono<App>()
  .use(requireSession)
  .get("/", account.account)
  .get("/keys", keys.list)
  .post("/keys", keys.create)
  .patch("/keys/:id", keys.update)
  .post("/keys/:id/rotate", keys.rotate)
  .delete("/keys/:id", keys.revoke)
  .get("/clips", account.clips)
  .get("/clips/:id", account.clip)
  .post("/clips", account.startClip)
  .post("/clips/:id/retry", account.retryClip)
  .get("/clips/:id/video", account.clipVideo)
  .get("/projects", account.projects)
  .get("/brand", account.brandKit)
  .put("/brand", account.saveBrandKit);

// you: users and their access keys
export const adminRoutes = new Hono<App>()
  .use(requireAdmin)
  .get("/beta-requests", admin.betaRequests)
  .post("/beta-requests/:id/approve", admin.approveBeta)
  .post("/users", admin.addUser)
  .post("/users/:id/keys", admin.addKey)
  .delete("/keys/:id", admin.dropKey)
  .get("/vm", admin.vm)
  .post("/vm/start", admin.vmStart);

// the Google VM
export const internalRoutes = new Hono<App>()
  .use(requireInternal)
  .post("/jobs/next", internal.next)
  .post("/jobs/:id/claim", internal.claim)
  .patch("/jobs/:id", internal.update)
  .post("/jobs/:id/progress", internal.progress)
  .put("/jobs/:id/video", internal.putVideo)
  .put("/jobs/:id/draft", internal.putDraft)
  .get("/jobs/:id/capture", captures.forJob)
  .get("/drafts/*", internal.getDraftFile);
