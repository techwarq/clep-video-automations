import type { Context } from "hono";
import browser from "../../engines/clep/capture/browser.py";
import clipPlan from "../../engines/clep/capture/clip_plan.py";
import featurePage from "../../engines/clep/capture/feature_page.py";
import featureRecorder from "../../engines/clep/capture/feature_recorder.py";
import hostedApi from "../../engines/clep/capture/hosted_api.py";
import pageScan from "../../engines/clep/capture/page_scan.py";
import privateBlur from "../../engines/clep/capture/private_blur.py";
import record from "../../engines/clep/capture/record.py";
import screencast from "../../engines/clep/capture/screencast.py";
import tourPlan from "../../engines/clep/capture/tour_plan.py";
import tourRecorder from "../../engines/clep/capture/tour_recorder.py";
import type { App } from "./types";

const FILES: Record<string, string> = {
  "record.py": record,
  "browser.py": browser,
  "feature_page.py": featurePage,
  "feature_recorder.py": featureRecorder,
  "page_scan.py": pageScan,
  "tour_recorder.py": tourRecorder,
  "screencast.py": screencast,
  "tour_plan.py": tourPlan,
  "hosted_api.py": hostedApi,
  "clip_plan.py": clipPlan,
  "private_blur.py": privateBlur,
};

export const recorderFile = (c: Context<App>) => {
  const file = FILES[c.req.param("file")!];
  return file === undefined
    ? c.json({ error: "not found", files: Object.keys(FILES) }, 404)
    : c.body(file, 200, { "Content-Type": "text/x-python; charset=utf-8", "Cache-Control": "public, max-age=300" });
};
