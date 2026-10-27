CREATE TABLE beta_requests (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name                text NOT NULL,
  email               text NOT NULL UNIQUE,
  product_url         text,
  status              text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved')),
  user_id             uuid REFERENCES users(id) ON DELETE SET NULL,
  access_code_hash    text,
  failed_signins      int NOT NULL DEFAULT 0,
  locked_until        timestamptz,
  approved_at         timestamptz,
  created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX beta_requests_status ON beta_requests(status, created_at);

CREATE TABLE sessions (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash  text NOT NULL UNIQUE,
  expires_at  timestamptz NOT NULL,
  revoked_at  timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX sessions_user ON sessions(user_id);
