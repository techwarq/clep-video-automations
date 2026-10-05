"""film3 agent mode: one strong model makes the whole film the way the hand-built films were made —
one film.html, tools to render / check / look / patch, iterate until excellent. Hard budget, prompt caching, patches.

    python3 motion.py film3 <name> --url … --request … --agent --yes      (FILM3_MODEL, FILM3_BUDGET_USD)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import List
from urllib.parse import urlparse

from . import context, library
from .fonts import build as fonts_build
from .mix import mix as mix_audio
from .render import encode, frames as render_frames
from . import brandui as BUI, check as K, lessons as LS, llm, music as M, sound as SND

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SK = HERE / "skills"
SKILLS = ("08_agent.md", "05_craft.md", "01_motion_rules.md", "02_story.md", "03_design.md", "07_brand_ui.md", "04_sound.md")
N_REFS = int(os.environ.get("FILM3_REFS", "0"))            # full reference films in the prompt (≈ 6–12k tokens each); 05_craft.md (their essence) replaces them
REFS = {  # hand-built reference films (device they show)
    "notch": (ROOT / "handbuilt/v3/notch/film.html", "desktop"),
    "truecaller": (ROOT / "handbuilt/v3/truecaller/film.html", "phone"),
    "maritime": (ROOT / "handbuilt/v2/maritime/film.html", "desktop"),
    "truemile": (ROOT / "handbuilt/v2/truemile/film.html", "phone"),
}


def _log(m):
    print(f"[agent] {time.strftime('%H:%M:%S')} {m}", flush=True)


def pick_refs(device: str, brand: str, n: int = 1) -> List[str]:
    """Up to n reference films (never the same brand — it would be copied). Device plays no role."""
    order = ["notch", "truecaller", "maritime", "truemile"]
    return [k for k in order if k not in brand and REFS[k][0].exists()][:n]


# ---------------------------------------------------------------- tools
TOOLS = [
    {"name": "music_grid", "description": "Plan the film's music: pick a library track and whole-bar sections; returns the film's bar table (times of every bar, energy, the DROP).",
     "parameters": {"type": "object", "properties": {"track": {"type": "string"}, "sections": {"type": "array", "items": {"type": "array", "items": {"type": "integer"}}}}, "required": ["track", "sections"]}},
    {"name": "plan", "description": "Free and required before write_file: commit the film as a short structured plan. It is validated against the music grid (payoff on the drop, big subjects, beats on bars) and saved to film/plan.json.",
     "parameters": {"type": "object", "properties": {
         "understanding": {"type": "string", "description": "one paragraph: the problem in the world, what changes when the product works, the objects that carry that change, the proof"},
         "world": {"type": "string"}, "signature": {"type": "string", "description": "the one visual idea this film is remembered by"},
         "carrier": {"type": "object", "properties": {"what": {"type": "string"}, "states": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "w": {"type": "number"}, "h": {"type": "number"}}}}}},
         "beats": {"type": "array", "items": {"type": "object", "properties": {"t0": {"type": "number"}, "t1": {"type": "number"}, "event": {"type": "string"}, "subject": {"type": "string"},
                   "subject_width_pct": {"type": "number"}, "words": {"type": "string"}, "action": {"type": "string"}}, "required": ["t0", "t1", "event", "subject_width_pct"]}},
         "payoff_t": {"type": "number", "description": "when the payoff lands (must be the drop)"}},
         "required": ["understanding", "carrier", "beats", "payoff_t"]}},
    {"name": "set_fonts", "description": "Localize fonts (Google Fonts names or the brand's font). Writes film/fonts.css; returns the family names to use in CSS.",
     "parameters": {"type": "object", "properties": {"display": {"type": "string"}, "ui": {"type": "string"}, "mono": {"type": "string"}}, "required": ["display", "ui"]}},
    {"name": "read_file", "description": "Read a skill, a reference film, or one of your film files.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write a file inside film/ (e.g. film/index.html, film/mix.json). Use once for the full film; afterwards patch with edit_file.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace an exact snippet in a film/ file (old must occur exactly once unless all=true).",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}, "all": {"type": "boolean"}}, "required": ["path", "old", "new"]}},
    {"name": "check", "description": "Free, local: script errors, hard cuts (frame jump detector), text overlaps, tiny text, headlines off frame, slow frames. Returns CLEAN or the problems with times.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "render_sheet", "description": "Render up to 12 moments of film/index.html as one labelled contact sheet image (you will see it).",
     "parameters": {"type": "object", "properties": {"times": {"type": "array", "items": {"type": "number"}}}, "required": ["times"]}},
    {"name": "render_frame", "description": "Render one moment at 1280×720 for a close look.", "parameters": {"type": "object", "properties": {"t": {"type": "number"}}, "required": ["t"]}},
    {"name": "view_ref", "description": "Look at one of the product's real UI reference crops by name.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "finish", "description": "Done: film/index.html and film/mix.json are final. Give the lessons you learned (mistakes you made and fixed).",
     "parameters": {"type": "object", "properties": {"summary": {"type": "string"}, "lessons": {"type": "array", "items": {"type": "string"}}}, "required": ["summary", "lessons"]}},
]


class Agent:
    def __init__(self, ctx: dict, work: Path, bu: dict, refs: List[str]):
        self.ctx, self.work, self.bu, self.refs = ctx, work, bu, refs
        self.film = work / "film"; self.film.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HERE / "runtime" / "core.js", self.film / "core.js")
        (self.film / "marks").mkdir(exist_ok=True)
        names = {"logo_svg": "logo.svg", "logo_png": "logo.png", "logo_on_dark": "logo_on_dark.png", "icon": "icon.png"}
        self.marks = []
        for k, p in ctx["marks"].items():
            if k in names:
                shutil.copyfile(p, self.film / "marks" / names[k]); self.marks.append("marks/" + names[k])
        self.grid = None
        self.plan_ok = False
        self.done = None
        self.looked = False            # a contact sheet seen since the film was written
        self.edits_since_look = 0
        self.checks_since_look = 0
        self.budget_warned = False
        self.images_pending: List[dict] = []

    # ---- path safety
    def _film_path(self, p: str) -> Path:
        q = (self.work / p).resolve() if not p.startswith("/") else Path(p).resolve()
        if not str(q).startswith(str(self.film.resolve())):
            raise ValueError("you may only write inside film/")
        return q

    def _read_path(self, p: str) -> Path:
        for base in (self.work, HERE, ROOT):
            q = (base / p).resolve()
            if q.exists() and any(str(q).startswith(str(r.resolve())) for r in (self.film, SK, ROOT / "handbuilt")):
                return q
        raise ValueError(f"cannot read {p} (readable: film/…, skills/…, handbuilt reference films)")

    def dur(self) -> float:
        try:
            return float(json.loads((self.film / "mix.json").read_text())["duration"])
        except Exception:
            return self.grid["dur"] if self.grid else 30.0

    # ---- tool implementations
    def call(self, name: str, a: dict) -> str:
        if name == "music_grid":
            self.grid = M.plan(a["track"], a["sections"])
            return M.table(self.grid) + f"\nFilm duration {self.grid['dur']}s. Use these times in seek() (e.g. const BAR={self.grid['bar']:.4f}, B = n => (n - 1) * BAR)."
        if name == "plan":
            return self.check_plan(a)
        if name == "set_fonts":
            look = {"display_font": a.get("display"), "ui_font": a.get("ui"), "mono_font": a.get("mono")}
            # Google Fonts first (complete, all weights); the site's own files only when the family isn't on Google
            css, loads, have = fonts_build(look, {}, self.ctx["project"].assets, self.film)
            if any(have.get(k) and have[k] != (look.get(f"{k}_font") or "").strip() for k in ("display", "ui")):
                css, loads, have = fonts_build(look, self.ctx["brand"], self.ctx["project"].assets, self.film)
            note = ""
            brand_fams = [v.get("family") for v in ((self.ctx["brand"].get("brand") or {}).get("fonts") or {}).values() if v.get("family")]
            chosen = " ".join(str(x).lower() for x in have.values())
            if brand_fams and not any(f.lower().split(" brand")[0] in chosen for f in brand_fams):
                note = (f"\nNOTE: the brand's own fonts are {brand_fams}; none is used. Use them unless the film's world clearly "
                        f"calls for another face (then say why in finish).")
            return f"film/fonts.css written. Families available: {json.dumps(have)}. await document.fonts.load for: {loads[:6]}" + note
        if name == "read_file":
            txt = self._read_path(a["path"]).read_text()
            return txt[:60000] + ("\n…(truncated)" if len(txt) > 60000 else "")
        if name == "write_file":
            if a["path"].endswith("index.html") and not self.plan_ok:
                return "ERROR: call plan first (free): the film must be planned and validated before it is written"
            p = self._film_path(a["path"]); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(a["content"])
            if a["path"].endswith("index.html"):
                self.looked, self.edits_since_look, self.checks_since_look = False, 0, 0
            return f"wrote {a['path']} ({len(a['content'])} chars)"
        if name == "edit_file":
            p = self._film_path(a["path"]); s = p.read_text(); n = s.count(a["old"])
            if n == 0:
                return "ERROR: old snippet not found (read the file and copy the exact text)"
            if n > 1 and not a.get("all"):
                return f"ERROR: old snippet occurs {n} times; add surrounding text or set all=true"
            p.write_text(s.replace(a["old"], a["new"]) if a.get("all") else s.replace(a["old"], a["new"], 1))
            if a["path"].endswith("index.html"):
                self.edits_since_look += 1
            return f"edited {a['path']} ({n if a.get('all') else 1} replacement)"
        if name == "check":
            idx = self.film / "index.html"
            if not idx.exists():
                return "film/index.html does not exist yet"
            g = self.film_grid()
            rep = K.film_check(idx, self.dur(), drop_t=g["drop_t"] if g else None)
            mx = self.mix_problems()
            self.checks_since_look += 1
            nudge = ""
            if self.checks_since_look >= 3 and rep != "CLEAN":
                nudge = ("\n\nLOOK NOW: three checks without looking at the film. Call render_sheet at each beat's hold before "
                         "any more layout fixes: a film that reads wrong is not fixed by moving things a few pixels.")
            return rep + (("\n\nMIX.JSON:\n" + mx) if mx else "") + nudge
        if name == "render_sheet":
            ts = [float(x) for x in a["times"]][:12]
            fs = K.stills(self.film / "index.html", [(f"{t:.2f}s", t) for t in ts], self.work / "shots" / time.strftime("%H%M%S"))
            sheet = K.sheet(fs, [f.stem.split("_", 1)[-1] for f in fs], self.work / "shots" / f"sheet_{time.strftime('%H%M%S')}.jpg", cols=4, w=480)
            self.images_pending.append(llm.image_part(sheet, max_w=1920))
            self.looked, self.edits_since_look, self.checks_since_look = True, 0, 0
            return (f"contact sheet of {len(fs)} frames attached below (in order: {', '.join(f'{t:.2f}s' for t in ts)})\n"
                    + self.review_brief(ts))
        if name == "render_frame":
            f = K.stills(self.film / "index.html", [(f"{a['t']:.2f}s", float(a["t"]))], self.work / "shots" / "frame")[0]
            self.images_pending.append(llm.image_part(f, max_w=1280))
            return f"frame at {a['t']:.2f}s attached below"
        if name == "view_ref":
            for s in self.bu.get("surfaces", []):
                if a["name"].lower() in s["name"].lower() and Path(s["file"]).exists():
                    self.images_pending.append(llm.image_part(Path(s["file"]), max_w=900))
                    return f"reference '{s['name']}' attached below. Anatomy: {s.get('anatomy', '')}"
            return "no such reference; names: " + ", ".join(s["name"] for s in self.bu.get("surfaces", []))
        if name == "finish":
            if not self.budget_warned and (self.film / "index.html").exists():
                if not self.looked:
                    return ("NOT YET: you have not looked at the film since writing it. render_sheet each beat's hold, the drop "
                            "and the end; compare every frame with its beat; fix what reads wrong; then finish.")
                if self.edits_since_look > 6:
                    return (f"NOT YET: {self.edits_since_look} edits since your last look. render_sheet the moments you changed, "
                            "confirm they read right, then finish.")
                g = self.film_grid()
                rep = K.film_check(self.film / "index.html", self.dur(), drop_t=g["drop_t"] if g else None)
                hard = [blk for blk in rep.split("\n\n") if blk.startswith(("HARD CUTS", "SCRIPT ERRORS", "SLIDESHOW"))]
                if hard:
                    return "NOT YET: these must be fixed before the film can finish:\n" + "\n\n".join(hard)
            self.done = a
            return "ok"
        return f"unknown tool {name}"

    def review_brief(self, ts: List[float]) -> str:
        """What to judge on a contact sheet: each frame against the beat the plan promised at that time."""
        try:
            beats = json.loads((self.film / "plan.json").read_text()).get("beats") or []
        except Exception:
            beats = []
        lines = []
        for t in ts:
            b = next((b for b in beats if float(b.get("t0", 0)) <= t < float(b.get("t1", 0))), None)
            if b:
                lines.append(f"- {t:.2f}s · planned: {b.get('event', '')} · words \"{b.get('words', '')}\" · action: {b.get('action', '')}")
        return ("JUDGE EACH FRAME AGAINST ITS BEAT:\n" + "\n".join(lines) + "\n" if lines else "") + (
            "For every frame: (1) does the picture SHOW what the words claim (if the words name a change, is that change "
            "visible)? (2) is every shape real content: no blank boxes standing in for photos, clips or documents? "
            "(3) is every name, number and claim on screen from the site, not invented? (4) does this moment look different "
            "from the one before, or is it the same layout with new text? List what fails, then patch only that.")

    def check_plan(self, a: dict) -> str:
        """Free validation of the plan against the music grid and the craft rules. PLAN OK unlocks write_file."""
        g = self.grid
        if not g:
            return "ERROR: call music_grid first, so the plan can be put on bars"
        out, beats = [], sorted(a.get("beats") or [], key=lambda b: float(b.get("t0", 0)))
        dur, bar, beat = g["dur"], g["bar"], g["beat"]
        if not 4 <= len(beats) <= 10:
            out.append(f"{len(beats)} beats: a film this long reads best as 4–10 events")
        if beats:
            if float(beats[0]["t0"]) > 0.3:
                out.append("the first beat must start at 0")
            if abs(float(beats[-1]["t1"]) - dur) > bar:
                out.append(f"beats end at {float(beats[-1]['t1']):.2f}s but the music is {dur:.2f}s: change sections or beats")
        for x, y in zip(beats, beats[1:]):
            if float(y["t0"]) - float(x["t1"]) > 0.3:
                out.append(f"gap {float(x['t1']):.2f}–{float(y['t0']):.2f}s: one continuous take, every moment belongs to a beat")
        for b in beats:
            t0 = float(b["t0"]); off = min(abs(t0 - round(t0 / beat) * beat), 9)
            if t0 > 0.3 and off > 0.06:
                out.append(f"beat '{b.get('event', '')[:40]}' starts at {t0:.2f}s, off the beat grid (beat {beat:.3f}s)")
        for b in beats[:-1]:
            if float(b.get("subject_width_pct", 0)) < 55:
                out.append(f"beat '{b.get('event', '')[:40]}': subject {b.get('subject_width_pct')}% of the width; plan 60–80%")
        for st in (a.get("carrier") or {}).get("states", []):
            if float(st.get("w", 0)) and float(st["w"]) < 1000:
                out.append(f"carrier state '{st.get('name', '')}' is {st['w']:.0f} px wide; on a 1920 frame plan ≥ 1100 (or scale its world)")
        long_words = [b["words"] for b in beats if len(str(b.get("words", "")).split()) > 8]
        if long_words:
            out.append(f"too many words on screen at once: {long_words[0][:60]}… (≤ 8 per beat)")
        if g.get("drop_t") is not None and abs(float(a.get("payoff_t", -9)) - g["drop_t"]) > 0.15:
            out.append(f"payoff at {float(a.get('payoff_t', -9)):.2f}s but the drop is at {g['drop_t']:.2f}s: move the payoff or choose other sections")
        if not any(str(b.get("action", "")).strip() for b in beats):
            out.append("no beat has a real action (a tap, a drag, a result appearing): the product must be USED on screen")
        (self.film / "plan.json").write_text(json.dumps(a, indent=1))
        if out:
            return "PLAN NEEDS CHANGES (fix and call plan again):\n" + "\n".join(f"- {x}" for x in out)
        self.plan_ok = True
        return f"PLAN OK (saved film/plan.json). Drop {g['drop_t']}s. Now write the whole film in one write_file."

    def mix_problems(self) -> str:
        p = self.film / "mix.json"
        if not p.exists():
            return "film/mix.json missing (write it before finishing)"
        try:
            m = json.loads(p.read_text())
        except Exception as e:
            return f"mix.json is not valid JSON: {e}"
        ids = {s["id"] for s in library.load()["sfx"]}; bad = [c.get("id") for c in m.get("cues", []) if c.get("id") not in ids]
        out = []
        if bad:
            out.append(f"unknown sfx ids: {sorted(set(bad))[:8]}")
        if not m.get("track") or not m.get("sections"):
            out.append("mix.json needs track + sections")
            return "\n".join(out)
        out += SND.problems(m, SND.read_events(self.film / "index.html"), M.plan(m["track"], m["sections"]))
        return "\n".join(out)

    def film_grid(self):
        """The film's bar grid: from mix.json when written, else from the last music_grid call."""
        try:
            m = json.loads((self.film / "mix.json").read_text())
            return M.plan(m["track"], m["sections"])
        except Exception:
            return self.grid


# ---------------------------------------------------------------- the loop
def system_prompt(agent: Agent) -> str:
    root = urlparse(agent.ctx["url"]).netloc.lower().replace("www.", "").split(".")
    brand = max(root, key=len) if root else ""           # e.g. "truecaller": never show a worked idea for the same brand
    sk = "\n\n".join((SK / n).read_text() for n in SKILLS)
    if brand:                                            # drop the essence block of a reference film about this same brand
        sk = re.sub(r"\*\*The [^\n]*<!-- ref:" + re.escape(brand) + r" -->.*?(?=\n\*\*The |\n## )", "", sk, flags=re.S)
        sk = "\n".join(l for l in sk.splitlines() if brand not in l.lower())
    sk = re.sub(r" <!-- ref:\w+ -->", "", sk)
    refs = "\n\n".join(f"## FULL REFERENCE FILM: {k} (learn the craft, never copy its product, world or words; draw everything in "
                       f"HTML/CSS/SVG/canvas)\n```html\n{REFS[k][0].read_text()}\n```" for k in agent.refs)
    return f"{sk}\n\n# LESSONS FROM PREVIOUS FILMS\n{LS.prompt_text()}" + (f"\n\n# REFERENCE FILMS\n{refs}" if refs else "")


def brand_line(doc: dict) -> str:
    b = doc.get("brand") or {}
    fonts = {k: v.get("family") for k, v in (b.get("fonts") or {}).items() if v.get("family")}
    return (f"fonts {json.dumps(fonts)} (set_fonts can load them) · colours {json.dumps(b.get('colors') or {})} · mode {b.get('mode') or '?'}. "
            f"Start from these; depart only on purpose.")


def brief(ctx: dict, bu: dict, request: str, seconds: float, marks: List[str]) -> str:
    p = ctx["intel"]["product"]
    keep = ("name", "one_liner", "audience", "problem", "core_objects", "core_actions", "aha", "differentiators", "proof", "tone")
    return (f"# MAKE THIS FILM\nREQUEST: {request or 'a launch film'} · about {seconds:.0f} seconds · url {ctx['url']}\n\n"
            f"PRODUCT (from the site crawl)\n{json.dumps({k: p.get(k) for k in keep if p.get(k)}, indent=1)}\n\n"
            f"THE PRODUCT'S REAL UI PIECES (use these looks whenever its UI appears; they do NOT decide the film's world)\n"
            f"{json.dumps(bu.get('ui_spec'), indent=1)}\n" + "\n".join(f"- {x['name']}: {x.get('anatomy', '')}" for x in bu.get("surfaces", [])) + "\n\n"
            f"BRAND (from the site): {brand_line(ctx['brand'])}\n"
            f"BRAND MARKS in film/: {marks or 'none (use the wordmark in the brand font)'}\n\n{M.catalog_text()}\n\n{M.sfx_text()}\n\n"
            f"THE WEBSITE (read it to understand the product: problem, promise, how it works, proof, exact copy)\n{ctx['pages_md'][:16000]}\n\n"
            f"Attached: website screenshots (to understand it), then the product's real UI crops (view_ref shows them larger).")


def _cached(text: str) -> list:
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def run_agent(ctx: dict, work: Path, bu: dict, request: str, seconds: float, max_turns: int = 40) -> Agent:
    dev = (bu.get("device") or {}).get("kind", "none")
    refs = pick_refs(dev, urlparse(ctx["url"]).netloc.lower(), N_REFS)
    ag = Agent(ctx, work, bu, refs)
    _log(f"model {llm.MODEL} · budget ${llm.BUDGET:.2f} · references {refs}")
    msgs = [{"role": "system", "content": _cached(system_prompt(ag))},
            {"role": "user", "content": [{"type": "text", "text": brief(ctx, bu, request, seconds, ag.marks)}]
             + [llm.image_part(s_, max_w=1100) for s_ in ctx["shots"][:2]] + BUI.ref_images(bu, 3)}]
    tools = [{"type": "function", "function": t} for t in TOOLS]
    warned = False
    last_cost = 0.0
    fix_model = os.environ.get("FILM3_FIX_MODEL")
    model = llm.MODEL
    for turn in range(max_turns):
        room = llm.BUDGET - llm.LEDGER["usd"]
        if room < max(0.12, last_cost * 2.2) and not warned and (ag.film / "index.html").exists():
            ag.budget_warned = True
            msgs.append({"role": "user", "content": "BUDGET NEARLY USED: this is your last turn with tools — write film/mix.json now (cues for the "
                         "visible actions, mute before the drop) and fix only the single most visible problem, then call finish."})
            warned = True
        elif room < last_cost * 1.1 or room <= 0:
            _log(f"budget: ${llm.LEDGER['usd']:.3f} spent, next turn would exceed ${llm.BUDGET:.2f} — stopping"); break
        # keep only the newest image in the conversation (older looks are paid for once)
        img_msgs = [i for i, m in enumerate(msgs) if isinstance(m.get("content"), list) and any(c.get("type") == "image_url" for c in m["content"])]
        for i in img_msgs[:-1]:
            if i > 1:
                msgs[i]["content"] = [c if c.get("type") != "image_url" else {"type": "text", "text": "[older image removed]"} for c in msgs[i]["content"]]
        # cache breakpoint on the newest message
        for m in msgs[2:]:
            if isinstance(m.get("content"), list):
                for c in m["content"]:
                    c.pop("cache_control", None)
        last = msgs[-1]
        if isinstance(last.get("content"), str):
            last["content"] = [{"type": "text", "text": last["content"]}]
        last["content"][-1]["cache_control"] = {"type": "ephemeral"}
        before = llm.LEDGER["usd"]
        try:
            r = llm.chat_tools(msgs, tools, tag=f"turn {turn + 1} {model.split('/')[-1]}", model=model)
        except llm.BudgetExceeded as e:
            _log(f"{e} — stopping"); break
        last_cost = llm.LEDGER["usd"] - before
        if fix_model and model != fix_model and (ag.film / "index.html").exists():
            model = fix_model; _log(f"film written — fix rounds continue on {fix_model}")
            for mm in msgs:                                     # thinking signatures belong to the first model
                mm.pop("reasoning_details", None)
        m = r["message"]
        msgs.append({k: v for k, v in m.items() if k in ("role", "content", "tool_calls", "reasoning_details") and v is not None})
        calls = m.get("tool_calls") or []
        if (m.get("content") or "").strip():
            _log(f"says: {m['content'].strip()[:200]}")
        if not calls:
            msgs.append({"role": "user", "content": "Continue with tools (check / render_sheet / edit_file / finish)."})
            continue
        ag.images_pending = []
        for c in calls:
            name = c["function"]["name"]
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
                out = ag.call(name, args)
            except Exception as e:
                out = f"ERROR: {e}"
            short = {k: (v if not isinstance(v, str) or len(v) < 80 else v[:60] + "…") for k, v in (args if isinstance(args, dict) else {}).items() if k != "content"}
            _log(f"{name} {json.dumps(short)[:140]} → {out.splitlines()[0][:120] if out else ''}")
            msgs.append({"role": "tool", "tool_call_id": c["id"], "content": out})
        if ag.images_pending:
            msgs.append({"role": "user", "content": [{"type": "text", "text": "Images from your render/view calls:"}] + ag.images_pending})
        if ag.done:
            _log(f"finished: {ag.done.get('summary', '')[:200]}")
            break
    return ag


def save_lessons(ag: Agent, name: str):
    LS.add(name, (ag.done or {}).get("lessons", []))


def render(ag: Agent, dest: Path, workers: int = 6) -> Path:
    if not (ag.film / "mix.json").exists():                    # the agent ran out before writing sound: music only
        g0 = ag.grid or M.plan("warm_indie_100", [[1, 14]])
        (ag.film / "mix.json").write_text(json.dumps({"track": g0["track"], "sections": g0["sections"], "duration": g0["dur"], "music_db": -3, "cues": []}))
    mx = json.loads((ag.film / "mix.json").read_text())
    g = M.plan(mx["track"], mx["sections"]); dur = float(mx.get("duration") or g["dur"])
    music = M.render(g, ag.work / "music.wav")
    events = SND.read_events(ag.film / "index.html") or SND.motion_events(K.scan(ag.film / "index.html", dur, every=99)[0])
    cues, mutes, notes = SND.complete(mx, events, g)
    if notes:
        _log(f"sound pass filled: {notes}")
    ev = [{"id": c["id"], "t": float(c["t"]), "gain": float(c.get("gain", -8)), **({"rate": c["rate"]} if c.get("rate") else {})} for c in cues]
    ev += [{"id": "@mute", "t": float(a), "dur": float(b)} for a, b in mutes]
    wav = mix_audio(ev, music, dur, library.LIB / "sfx", ag.work / "mix.wav", music_db=float(mx.get("music_db", -3)))
    fr = ag.work / "frames"
    if fr.exists():
        shutil.rmtree(fr)
    render_frames(ag.film / "index.html", fr, dur, fps=60, sub=2, workers=workers)
    return encode(fr, wav, dest)


def rerender(name: str, workers: int = 6) -> Path:
    """Render a film the agent already wrote (projects/<name>/film3/agent/film): no model calls. Used for retries."""
    from types import SimpleNamespace
    from director.paths import Project
    pr = Project(name)
    work = pr.dir / "film3" / "agent"
    if not (work / "film" / "index.html").exists():
        raise SystemExit(f"no saved film for {name} ({work / 'film'})")
    dest = pr.dir / "renders" / f"agent_{name}.mp4"
    render(SimpleNamespace(film=work / "film", work=work, grid=None), dest, workers)
    _log(f"re-rendered {name} · model spend $0.000 → {dest}")
    return dest


def run(name: str, url: str, request: str = "", seconds: float = 30, workers: int = 6, render_film: bool = True) -> Path:
    t0 = time.time()
    ctx = context.build(name, url)
    pr = ctx["project"]; base = pr.dir / "film3"
    st = json.loads((base / "state.json").read_text()) if (base / "state.json").exists() else {}
    bu = st.get("brandui") or BUI.study(ctx, base)
    dry = llm.MODEL == "dry"
    work = base / ("agent_dry" if dry else "agent")             # a dry run never touches the real agent folder
    if work.exists():
        shutil.rmtree(work)
    ag = run_agent(ctx, work, bu, request, seconds)
    if not dry:                                                 # a scripted run teaches nothing
        save_lessons(ag, name)
    g = ag.film_grid()
    final = K.film_check(ag.film / "index.html", ag.dur(), drop_t=g["drop_t"] if g else None) if (ag.film / "index.html").exists() else "no film"
    if not dry:
        LS.record_checks(final, name)
    _log(f"final check: {final.splitlines()[0]}")
    dest = pr.dir / "renders" / f"agent{'_dry' if dry else ''}_{name}.mp4"
    if render_film:
        render(ag, dest, workers)
    _log(f"done in {(time.time() - t0) / 60:.1f} min · model spend ${llm.LEDGER['usd']:.3f} over {llm.LEDGER['calls']} calls → {dest}")
    return dest
