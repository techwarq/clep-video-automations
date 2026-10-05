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
};

export type Engine = "reels" | "motion";
export const ENGINES: Engine[] = ["reels", "motion"];
export type JobStatus = "queued" | "running" | "done" | "failed";

export type Auth = { userId: string; keyId: string; engines: Engine[] };
export type App = { Bindings: Env; Variables: { auth: Auth } };

// Postgres: uuid/text come back as strings, jsonb as objects, numeric + bigint as strings, timestamptz as strings
export type Job = {
  id: string; user_id: string; key_id: string | null; engine: Engine; status: JobStatus; input: unknown;
  attempts: number; error: string | null; cost_usd: string; created_at: string; updated_at: string;
};
export type Video = { id: string; job_id: string; user_id: string; r2_key: string; bytes: string; created_at: string };
export type Draft = { job_id: string; user_id: string; r2_key: string; bytes: string; updated_at: string };

// what the VM receives; draft_key set = re-render the saved draft, no model calls
export type JobMessage = { id: string; user_id: string; engine: Engine; input: unknown; draft_key?: string };
