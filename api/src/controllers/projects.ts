import type { Context } from "hono";
import { listProjects, syncProject, type FeatureInput } from "../projects";
import type { App } from "../types";

const MAX_FEATURES = 200;
const SLUG = /^[a-z0-9][a-z0-9-]{0,63}$/;

const text = (value: unknown, max: number) => (typeof value === "string" && value.trim() ? value.trim().slice(0, max) : null);

function features(value: unknown): FeatureInput[] | string {
  if (!Array.isArray(value)) return "features must be a list";
  if (value.length > MAX_FEATURES) return `at most ${MAX_FEATURES} features`;
  const found: FeatureInput[] = [];
  for (const item of value as Record<string, unknown>[]) {
    const slug = text(item?.slug, 64);
    if (!slug || !SLUG.test(slug)) return `feature slug must be kebab-case: ${JSON.stringify(item?.slug)}`;
    if (found.some((f) => f.slug === slug)) return `duplicate feature slug: ${slug}`;
    found.push({ slug, name: text(item.name, 120) ?? slug, route: text(item.route, 300),
      description: text(item.description, 500), steps: Array.isArray(item.steps) ? item.steps : undefined });
  }
  return found;
}

export async function sync(c: Context<App>) {
  const body = await c.req.json<Record<string, unknown>>().catch(() => ({} as Record<string, unknown>));
  const name = text(body.name, 120);
  if (!name) return c.json({ error: "name is required (the project or repo name)" }, 400);
  const list = features(body.features ?? []);
  if (typeof list === "string") return c.json({ error: list }, 400);
  const project = await syncProject(c.env, c.get("auth").userId, {
    name, repo_url: text(body.repo_url, 300), app_url: text(body.app_url, 300), framework: text(body.framework, 60), features: list,
  });
  return c.json({ project });
}

export const list = async (c: Context<App>) => c.json({ projects: await listProjects(c.env, c.get("auth").userId) });
