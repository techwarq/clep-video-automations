CREATE TABLE brand_kits (
  user_id     uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  kit         jsonb NOT NULL,
  updated_at  timestamptz NOT NULL DEFAULT now()
);
