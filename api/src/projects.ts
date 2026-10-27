import { db } from "./db";
import type { Env } from "./types";

export type FeatureInput = { slug: string; name: string; route: string | null; description: string | null; steps: unknown };
export type ProjectInput = { name: string; repo_url: string | null; app_url: string | null; framework: string | null; features: FeatureInput[] };

export async function syncProject(env: Env, userId: string, project: ProjectInput) {
  const sql = db(env);
  const [saved] = await sql`
    INSERT INTO projects (user_id, name, repo_url, app_url, framework)
    VALUES (${userId}, ${project.name}, ${project.repo_url}, ${project.app_url}, ${project.framework})
    ON CONFLICT (user_id, name) DO UPDATE SET repo_url = excluded.repo_url, app_url = excluded.app_url,
      framework = excluded.framework, synced_at = now()
    RETURNING id, name, repo_url, app_url, framework, synced_at`;
  const slugs = project.features.map((f) => f.slug);
  await sql.transaction([
    sql`DELETE FROM features WHERE project_id = ${saved.id} AND NOT (slug = ANY(${slugs}))`,
    ...project.features.map((f) => sql`
      INSERT INTO features (project_id, slug, name, route, description, steps)
      VALUES (${saved.id}, ${f.slug}, ${f.name}, ${f.route}, ${f.description}, ${f.steps === undefined ? null : JSON.stringify(f.steps)}::jsonb)
      ON CONFLICT (project_id, slug) DO UPDATE SET name = excluded.name, route = excluded.route,
        description = excluded.description, steps = excluded.steps, updated_at = now()`),
  ]);
  return { ...saved, features: slugs.length };
}

export const listProjects = async (env: Env, userId: string) =>
  db(env)`
    SELECT p.id, p.name, p.repo_url, p.app_url, p.framework, p.synced_at,
      COALESCE(json_agg(json_build_object('slug', f.slug, 'name', f.name, 'route', f.route, 'description', f.description)
        ORDER BY f.name) FILTER (WHERE f.id IS NOT NULL), '[]') AS features
    FROM projects p LEFT JOIN features f ON f.project_id = p.id
    WHERE p.user_id = ${userId} GROUP BY p.id ORDER BY p.synced_at DESC`;
