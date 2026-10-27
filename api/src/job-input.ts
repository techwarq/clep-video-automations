import { isUuid } from "./db";
import { isPublicWebUrl, urlsInText } from "./public-url";
import type { Engine } from "./types";

type Body = Record<string, unknown>;
type Problem = string | null;

export const MAX_INPUT_BYTES = 64 * 1024;
const MAX_TEXT = 2000;
const MAX_STEPS = 60;
const MAX_SECTIONS = 20;
const NAME = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/;
const SIZE = /^\d{2,4}x\d{2,4}$/;
const DEMO_FILE = /^demo\/[A-Za-z0-9][A-Za-z0-9_.-]*$/;
const STEP_ACTIONS = ["type", "click", "upload", "wait", "press", "scroll", "hover", "goto"];
const CHOICES: Record<string, string[]> = {
  kind: ["auto", "tour", "feature", "mockup", "launch"],
  style: ["minimal", "saas", "cinematic", "apple"],
  movement: ["calm", "standard", "dynamic"],
  aspect: ["16:9", "1:1", "4:5", "9:16"],
  quality: ["720p", "1080p", "1440p", "4k"],
};
const SHORT_TEXT_FIELDS = ["query", "goal", "audience", "voiceover"];
const OBJECT_FIELDS = ["intro", "look", "outro"];
const DEVICES = ["", "browser", "macbook"];
const SOUNDS: unknown[] = [true, false, "warm", "cold"];
const CURSOR = /^[a-z0-9# ]{0,60}$/i;
const STORY_TEXT: Record<string, string[]> = { intro: ["title"], outro: ["title", "cta", "brand"] };

const isText = (value: unknown, max = MAX_TEXT): value is string => typeof value === "string" && value.length <= max;
const isObject = (value: unknown): value is Body => typeof value === "object" && value !== null && !Array.isArray(value);
const isNumberBetween = (value: unknown, low: number, high: number) =>
  typeof value === "number" && Number.isFinite(value) && value >= low && value <= high;
const firstProblem = (...checks: (() => Problem)[]) => checks.reduce<Problem>((found, check) => found ?? check(), null);

function promptProblem(prompt: unknown): Problem {
  if (prompt === undefined) return null;
  if (!isText(prompt) || !prompt.trim()) return `prompt must be text up to ${MAX_TEXT} characters`;
  const blocked = urlsInText(prompt).find((url) => !isPublicWebUrl(url));
  return blocked ? `the prompt links to ${blocked}: only public http(s) addresses can be recorded` : null;
}

const urlProblem = (field: string, value: unknown): Problem =>
  value === undefined || isPublicWebUrl(value) ? null : `${field} must be a public http(s) address (not localhost, a private network or a file)`;

function stepProblem(step: unknown, index: number): Problem {
  const where = `steps[${index}]`;
  if (!isObject(step)) return `${where} must be an object`;
  const action = String(step.action ?? "").toLowerCase();
  if (!STEP_ACTIONS.includes(action)) return `${where}.action must be one of ${STEP_ACTIONS.join(", ")}`;
  if (action === "goto") return urlProblem(`${where}.url`, step.url ?? "");
  if (step.file !== undefined && !(typeof step.file === "string" && DEMO_FILE.test(step.file))) {
    return `${where}.file: hosted recordings can only upload Clep's demo files; record locally to upload your own`;
  }
  return null;
}

function stepsProblem(steps: unknown): Problem {
  if (steps === undefined) return null;
  if (!Array.isArray(steps) || steps.length > MAX_STEPS) return `steps must be a list of up to ${MAX_STEPS} steps`;
  return firstProblem(...steps.map((step, index) => () => stepProblem(step, index)));
}

function sectionsProblem(sections: unknown): Problem {
  if (sections === undefined || isText(sections, 500)) return null;
  const isList = Array.isArray(sections) && sections.length <= MAX_SECTIONS && sections.every((s) => isText(s, 80));
  return isList ? null : `sections must be text or a list of up to ${MAX_SECTIONS} names`;
}

function storyProblem(body: Body): Problem {
  for (const field of OBJECT_FIELDS) {
    if (body[field] !== undefined && !isObject(body[field])) return `${field} must be an object`;
  }
  const look = (body.look ?? {}) as Body;
  if (look.device !== undefined && !DEVICES.includes(look.device as string)) return "look.device must be browser or macbook";
  if (look.cursor !== undefined && !(typeof look.cursor === "string" && CURSOR.test(look.cursor))) return "look.cursor must be words like \"hand halo\"";
  if (look.sound !== undefined && !SOUNDS.includes(look.sound)) return "look.sound must be true, false, warm or cold";
  for (const flag of ["glow", "reflection"]) {
    if (look[flag] !== undefined && typeof look[flag] !== "boolean") return `look.${flag} must be true or false`;
  }
  for (const [part, fields] of Object.entries(STORY_TEXT)) {
    const story = (body[part] ?? {}) as Body;
    const long = fields.find((field) => story[field] !== undefined && !isText(story[field], 80));
    if (long) return `${part}.${long} must be text up to 80 characters`;
  }
  return null;
}

export function lookProblem(body: Body): Problem {
  const story = storyProblem(body);
  if (story) return story;
  for (const [field, choices] of Object.entries(CHOICES)) {
    if (body[field] !== undefined && !choices.includes(body[field] as string)) return `${field} must be one of ${choices.join(", ")}`;
  }
  if (body.bg !== undefined && !(isText(body.bg, 200) && !/^\s*image:/i.test(body.bg))) {
    return "bg must be a preset, gradient or solid colour";
  }
  if (body.size !== undefined && !(typeof body.size === "string" && SIZE.test(body.size))) return "size must look like 1920x1080";
  if (body.duration !== undefined && !isNumberBetween(body.duration, 1, 180)) return "duration must be 1–180 seconds";
  if (body.fps !== undefined && !(Number.isInteger(body.fps) && isNumberBetween(body.fps, 24, 60))) return "fps must be 24–60";
  return null;
}

function textFieldsProblem(body: Body): Problem {
  if (body.name !== undefined && !(typeof body.name === "string" && NAME.test(body.name))) {
    return "name must be the data-clep name: letters, numbers, - _ . (up to 64)";
  }
  const longText = SHORT_TEXT_FIELDS.find((field) => body[field] !== undefined && !isText(body[field], 500));
  if (longText) return `${longText} must be text up to 500 characters`;
  for (const flag of ["captions", "ai"]) {
    if (body[flag] !== undefined && typeof body[flag] !== "boolean") return `${flag} must be true or false`;
  }
  const isSelectorList = Array.isArray(body.private) && body.private.every((s) => isText(s, 200));
  return body.private === undefined || isSelectorList ? null : "private must be a list of CSS selectors";
}

function clepProblem(body: Body): Problem {
  if (body.prompt === undefined && body.url === undefined && body.capture === undefined) return "prompt, url or capture is required";
  if (body.capture !== undefined && !(typeof body.capture === "string" && isUuid(body.capture))) {
    return "capture must be a capture_id from POST /api/captures";
  }
  const recordsOnTheRenderer = body.capture === undefined;
  return firstProblem(
    () => (recordsOnTheRenderer ? urlProblem("url", body.url) : isText(body.url ?? "") ? null : "url must be text"),
    () => promptProblem(body.prompt),
    () => stepsProblem(body.steps),
    () => sectionsProblem(body.sections),
    () => lookProblem(body),
    () => textFieldsProblem(body),
  );
}

function motionProblem(body: Body): Problem {
  if (!isText(body.request) || !body.request.trim()) return "request is required (text up to 2000 characters)";
  if (body.seconds !== undefined && !isNumberBetween(body.seconds, 1, 180)) return "seconds must be 1–180";
  return isPublicWebUrl(body.url) ? null : "url must be a public http(s) address (not localhost, a private network or a file)";
}

const reelsProblem = (body: Body): Problem =>
  isText(body.prompt) && body.prompt.trim() ? null : `prompt is required (text up to ${MAX_TEXT} characters)`;

const PROBLEMS: Record<Engine, (body: Body) => Problem> = { reels: reelsProblem, motion: motionProblem, clep: clepProblem };

export function inputProblem(engine: Engine, body: unknown): Problem {
  if (!isObject(body)) return "the request body must be a JSON object";
  if (JSON.stringify(body).length > MAX_INPUT_BYTES) return `the request is too large (over ${MAX_INPUT_BYTES / 1024} KB)`;
  return PROBLEMS[engine](body);
}
