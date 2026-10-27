ALTER TABLE users ADD COLUMN plan text NOT NULL DEFAULT 'beta' CHECK (plan IN ('free', 'beta', 'pro', 'studio'));

ALTER TABLE access_keys ADD COLUMN last_used_at timestamptz;

ALTER TABLE jobs ADD COLUMN stage text;
ALTER TABLE jobs ADD COLUMN progress int NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100);
ALTER TABLE jobs ADD COLUMN export_seconds numeric(10, 2);

CREATE TABLE usage_ledger (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  job_id      uuid REFERENCES jobs(id) ON DELETE SET NULL,
  kind        text NOT NULL CHECK (kind IN ('export', 'refund', 'grant')),
  seconds     numeric(10, 2) NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX usage_ledger_user ON usage_ledger(user_id, created_at);
CREATE UNIQUE INDEX usage_ledger_one_export_per_job ON usage_ledger(job_id) WHERE kind = 'export';

CREATE TABLE projects (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name        text NOT NULL,
  repo_url    text,
  app_url     text,
  framework   text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  synced_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, name)
);

CREATE TABLE features (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  slug        text NOT NULL,
  name        text NOT NULL,
  route       text,
  description text,
  steps       jsonb,
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (project_id, slug)
);
