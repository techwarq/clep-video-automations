ALTER TABLE access_keys DROP COLUMN minute_limit;
ALTER TABLE access_keys ADD COLUMN expires_at timestamptz;
ALTER TABLE users ALTER COLUMN plan SET DEFAULT 'free';
