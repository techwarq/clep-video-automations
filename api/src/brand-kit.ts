import { db } from "./db";
import { lookProblem } from "./job-input";
import type { Env } from "./types";

export type BrandKit = Record<string, unknown>;

const KIT_FIELDS = ["style", "bg", "aspect", "movement", "captions", "look", "intro", "outro"];
const MERGED_FIELDS = ["look", "intro", "outro"];

export function kitProblem(kit: unknown): string | null {
  if (typeof kit !== "object" || kit === null || Array.isArray(kit)) return "the brand kit must be a JSON object";
  const unknown = Object.keys(kit).find((field) => !KIT_FIELDS.includes(field));
  if (unknown) return `the brand kit has no ${unknown} setting (allowed: ${KIT_FIELDS.join(", ")})`;
  const captions = (kit as BrandKit).captions;
  if (captions !== undefined && typeof captions !== "boolean") return "captions must be true or false";
  return lookProblem(kit as BrandKit);
}

export async function loadKit(env: Env, userId: string): Promise<BrandKit | null> {
  const [row] = await db(env)`SELECT kit FROM brand_kits WHERE user_id = ${userId}`;
  return (row?.kit as BrandKit) ?? null;
}

export const saveKit = (env: Env, userId: string, kit: BrandKit) =>
  db(env)`
    INSERT INTO brand_kits (user_id, kit) VALUES (${userId}, ${JSON.stringify(kit)}::jsonb)
    ON CONFLICT (user_id) DO UPDATE SET kit = excluded.kit, updated_at = now()`;

export function withKit(input: BrandKit, kit: BrandKit | null): BrandKit {
  if (!kit) return input;
  const merged: BrandKit = { ...kit, ...input };
  for (const field of MERGED_FIELDS) {
    if (kit[field] || input[field]) merged[field] = { ...(kit[field] as BrandKit), ...(input[field] as BrandKit) };
  }
  return merged;
}
