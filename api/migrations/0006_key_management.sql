ALTER TABLE access_keys ADD COLUMN last4 text;
ALTER TABLE access_keys ADD COLUMN minute_limit int CHECK (minute_limit IS NULL OR minute_limit > 0);
ALTER TABLE access_keys ADD COLUMN disabled_at timestamptz;
ALTER TABLE access_keys ADD COLUMN replaced_by uuid REFERENCES access_keys(id) ON DELETE SET NULL;
CREATE INDEX access_keys_active ON access_keys(user_id) WHERE revoked_at IS NULL;
CREATE INDEX jobs_key_month ON jobs(key_id, created_at);
