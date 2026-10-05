# video-automation

One backend for every video engine.

```
client ──► api/  (Cloudflare Worker)          vm/  (Google VM, Python)
 access    routes → controllers                pulls jobs from the queue
 key       Neon Postgres (users,   ── Queue ─► router → services/{reels,motion}
              drafts, videos)                  runs engines/{reels,motion}
           R2 videos/ + drafts/ ◄── upload ─── film source (draft) + mp4
           /internal/* ◄──── status + cost ───
```

| folder | what |
|---|---|
| `api/` | Cloudflare Worker: public API, queue producer, R2 storage; data in Neon Postgres |
| `vm/` | Worker process on the Google VM: pulls jobs, runs the right engine, uploads, reports back |
| `engines/reels` | the reels engine (from `allore-pipelines/pipeline`) |
| `engines/motion` | the launch-film engine (from `allore-pipelines/pipeline_motion`) |
| `deploy/` | `create-vm.sh` (once) + `startup.sh` (every boot: pull image → run worker → power off when idle) |
| `Dockerfile` | engine image: `vm/` + `engines/`, Chromium, ffmpeg |
| `.github/workflows/` | CI/CD: `deploy-api.yml` → Cloudflare, `deploy-engine.yml` → Google VM |

## Database (Neon Postgres, `api/migrations/*.sql`)

Project `gentle-cell-80493280`: branch `production` for the deployed API, branch `dev` for `wrangler dev`
(`api/.dev.vars`). `npm run migrate` (in `api/`) applies new migration files; CI runs it before each deploy.

| table | holds |
|---|---|
| `users` | who can use the API |
| `access_keys` | a user's keys (stored as sha-256; the key is shown once) and the `engines` each key may call |
| `jobs` | one request each: engine, input, status, attempts, error, model cost (summed over attempts) |
| `drafts` | the film source a job produced (R2 `drafts/<user>/<job>.tar.gz`); a retry re-renders it with no model spend |
| `videos` | finished videos per user (R2 `videos/<user>/<job>.mp4`) |

## API

| route | key | does |
|---|---|---|
| `POST /v1/reels` `{prompt, style?, tts?}` | access key | new reels job → `{id}` |
| `POST /v1/motion` `{url, request, seconds?}` | access key | new launch-film job → `{id}` |
| `GET /v1/jobs`, `GET /v1/jobs/:id` | access key | your jobs: status, attempts, cost, video, has_draft |
| `POST /v1/jobs/:id/retry` | access key | re-run a failed job; with a draft it only re-renders |
| `GET /v1/videos`, `GET /v1/videos/:id` | access key | your videos; the second streams the mp4 |
| `POST /admin/users` `{email, name?}` | `ADMIN_KEY` | add a user |
| `POST /admin/users/:id/keys` `{engines?, label?}` | `ADMIN_KEY` | new access key (returned once) |
| `DELETE /admin/keys/:id` | `ADMIN_KEY` | revoke a key |
| `/internal/*` | `INTERNAL_KEY` | the VM: job status + cost, video and draft uploads, draft download |

A user only ever sees their own jobs and videos; a key used for an engine it isn't allowed gets `403`.

## Job lifecycle

`queued → running → done | failed` (→ `POST /retry` → `queued` again — the only way a job runs twice)

1. `POST /v1/motion` → `jobs` row (with `user_id`), message on the `video-jobs` queue.
2. The VM pulls it, marks it `running` (attempts + 1) and runs the engine, streaming its model spend.
3. It uploads the mp4 (`videos` row) and marks the job `done` with the cost, or `failed` with the error and
   the cost so far. Either way, whatever film the model wrote is saved as the job's draft.
4. A retry of a failed job with a draft restores the film and only renders it: no second model bill.
   Reels keeps no draft yet, so a reels retry runs again in full.

## Adding an engine

1. `engines/<name>/` — the engine code.
2. `vm/services/<name>.py` — `run(job_id, input, draft) -> (mp4, cost)`, `draft(job_id)`, `cleanup(job_id)`;
   register it in `vm/router.py`.
3. `api/src/controllers/engines.ts` — add its input check; add the route in `api/src/routes.ts` and the name to
   `ENGINES` in `api/src/types.ts`.

## Deploy (CI/CD on push to `main`)

| workflow | triggers on | does |
|---|---|---|
| `deploy-api.yml` | `api/**` | type-check → `npm run migrate` (Neon) → `wrangler deploy` |
| `deploy-engine.yml` | `engines/**`, `vm/**`, `Dockerfile` | build image → push `:latest`; the VM picks it up on its next boot |

GitHub settings:

- secrets: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `DATABASE_URL` (Neon production), `GCP_SA_KEY` (service account JSON:
  Artifact Registry Writer + Compute Instance Admin + IAP-secured Tunnel User)
- variables: `GCP_PROJECT`

One-time setup:

```bash
# Cloudflare
cd api
npx wrangler r2 bucket create video-automation
npx wrangler queues create video-jobs
npm run migrate                                 # tables on Neon production (.env.local)
npm run secrets                                 # ADMIN_KEY + INTERNAL_KEY (api/.env) + DATABASE_URL (.env.local)

# Google
gcloud artifacts repositories create video-automation --repository-format docker --location <region>
# on the VM (needs the Artifact Registry Reader scope / role):
bash deploy/vm-bootstrap.sh                     # installs Docker
# then fill vm/.env.example → /opt/video-automation/.env
```

## The render VM (on demand)

`video-worker` is a Spot `e2-standard-4` in `us-east4-a`. It is **off** unless there is work:

1. A job is queued → the API sets a `pending` flag (KV) and starts the VM (`src/gcp.ts`).
2. On boot `deploy/startup.sh` pulls the latest image, reads its settings from Secret Manager (`video-worker-env`)
   and runs the worker.
3. When the queue has been empty for 10 minutes the worker exits and the VM powers off.
4. Every minute the API checks the flag: if jobs are still queued and the VM is down (it was shutting down, or
   Spot reclaimed it), it starts it again. With no pending work this is one KV read: no database, no GCP call.

`GET /admin/vm` shows its state; `POST /admin/vm/start` starts it by hand. A job runs once per request:
the worker claims it (`queued → running`) and acks its message before rendering, so the queue never redelivers it.
If the VM dies mid-job (Spot reclaim, deploy), the API marks the job `failed` after 90 min of `running`; it runs
again only on `POST /v1/jobs/:id/retry` (from its draft if it has one).
