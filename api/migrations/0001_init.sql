-- users and what they may use
CREATE TABLE users (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email       text NOT NULL UNIQUE,
  name        text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- access ids: one user can hold several keys; each key lists the engines it may call
CREATE TABLE access_keys (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  key_hash    text NOT NULL UNIQUE,                 -- sha-256 of the key; the key itself is shown once
  prefix      text NOT NULL,                        -- first chars, to recognise a key in lists
  label       text,
  engines     text[] NOT NULL DEFAULT '{reels,motion}',
  created_at  timestamptz NOT NULL DEFAULT now(),
  revoked_at  timestamptz
);
CREATE INDEX access_keys_user ON access_keys(user_id);

-- one request = one job (api → queue → worker)
CREATE TABLE jobs (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  key_id      uuid REFERENCES access_keys(id) ON DELETE SET NULL,
  engine      text NOT NULL CHECK (engine IN ('reels', 'motion')),
  status      text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'done', 'failed')),
  input       jsonb NOT NULL,
  attempts    int NOT NULL DEFAULT 0,
  error       text,
  cost_usd    numeric(10, 4) NOT NULL DEFAULT 0,    -- model spend, summed over attempts
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX jobs_user ON jobs(user_id, created_at DESC);
CREATE INDEX jobs_status ON jobs(status, created_at);

-- the film source a job produced (html, plan, mix): a retry re-renders it without paying the model again
CREATE TABLE drafts (
  job_id      uuid PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  r2_key      text NOT NULL,
  bytes       bigint NOT NULL,
  updated_at  timestamptz NOT NULL DEFAULT now()
);

-- finished videos, owned by a user
CREATE TABLE videos (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id      uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  r2_key      text NOT NULL,
  bytes       bigint NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX videos_user ON videos(user_id, created_at DESC);
CREATE INDEX videos_job ON videos(job_id, created_at DESC);
