import type { Context, MiddlewareHandler } from "hono";
import { cors } from "hono/cors";
import type { App } from "./types";

const allowedOrigins = (c: Context<App>) => c.env.BROWSER_ORIGINS.split(",").map((origin) => origin.trim()).filter(Boolean);

export const browserCors: MiddlewareHandler<App> = cors({
  origin: (origin, c) => (allowedOrigins(c).includes(origin) ? origin : null),
  allowHeaders: ["Authorization", "Content-Type"],
  allowMethods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
  maxAge: 600,
});
