export type Env = {
  DATABASE_URL: string;  // Neon Postgres (pooled)
  VIDEOS: R2Bucket;
  JOBS: Queue<JobMessage>;
  STATE: KVNamespace;
  ADMIN_KEY: string;     // you: create users and access keys
  INTERNAL_KEY: string;  // the Google VM
  GCP_SA_KEY: string;    // service account that may start the render VM
  GCP_PROJECT: string;
  GCP_ZONE: string;
  GCP_VM: string;
  RESEND_API_KEY: string;
  EMAIL_FROM: string;
  ADMIN_EMAIL: string;
  ADMIN_EMAILS: string;
  PLATFORM_URL: string;
  API_URL: string;
  BROWSER_ORIGINS: string;
  SIGNIN_LIMITER: RateLimit;
  RESERVE_LIMITER: RateLimit;
  KEY_RATE_FREE: RateLimit;
  KEY_RATE_BETA: RateLimit;
  KEY_RATE_PRO: RateLimit;
  KEY_RATE_STUDIO: RateLimit;
};

export type Engine = "reels" | "motion" | "clep";
export const ENGINES: Engine[] = ["reels", "motion", "clep"];
export type JobStatus = "queued" | "running" | "done" | "failed";

export type Plan = "free" | "beta" | "pro" | "studio";
export type Auth = { userId: string; keyId: string; engines: Engine[]; plan: Plan; minuteLimit: number | null };
export type Owner = { userId: string; keyId: string | null };
export type SessionUser = { id: string; email: string; name: string | null };
export type App = { Bindings: Env; Variables: { auth: Auth; session: SessionUser } };

// Postgres: uuid/text come back as strings, jsonb as objects, numeric + bigint as strings, timestamptz as strings
export type Job = {
  id: string; user_id: string; key_id: string | null; engine: Engine; status: JobStatus; input: unknown;
  attempts: number; error: string | null; cost_usd: string; result: unknown | null; created_at: string; updated_at: string;
  stage: string | null; progress: number; export_seconds: string | null;
};
export type Video = { id: string; job_id: string; user_id: string; r2_key: string; bytes: string; created_at: string };
export type Draft = { job_id: string; user_id: string; r2_key: string; bytes: string; updated_at: string };

// what the VM receives; draft_key set = re-render the saved draft, no model calls
export type JobMessage = { id: string; user_id: string; engine: Engine; input: unknown; draft_key?: string };

export type BetaRequest = {
  id: string; name: string; email: string; product_url: string | null; status: "pending" | "approved";
  user_id: string | null; access_code_hash: string | null; failed_signins: number; locked_until: string | null;
  approved_at: string | null; created_at: string;
};
