"""Load skill files (skills/*.md) and gold examples as model context."""

from __future__ import annotations

import re

from reels import config

STYLES = {
    "meme": ("styles/meme.md", ["meme_vs.html"]),
    "pinterest_edit": ("styles/pinterest-edit.md",
                       ["pinterest_editorial.html", "pinterest_doc.html", "pinterest_collage.html"]),
    "motion_explainer": ("styles/motion-explainer.md", ["motion_explainer.html"]),
    "talking_head": ("styles/talking-head.md", ["talking_head.html"]),
}


def read(name: str) -> str:
    """Skill text without its frontmatter."""
    text = (config.SKILLS_DIR / name).read_text()
    return re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S).strip()


def example(name: str) -> str:
    return (config.SKILLS_DIR / "examples" / name).read_text()


def style_skill(style: str) -> str:
    return read(STYLES[style][0])


def pick_example(style: str, look: str = "") -> str:
    files = STYLES[style][1]
    if style == "pinterest_edit" and re.search(r"collage|recap|commentary|essay|reaction|card", look or "", re.I):
        return example(files[2])
    if style == "pinterest_edit" and re.search(r"doc|graph|paper|stamp|bracket", look or "", re.I):
        return example(files[1])
    return example(files[0])


def planning_context() -> str:
    parts = [read("plan.md"), read("reel-craft.md")]
    parts += [f"## Style: {s}\n\n{style_skill(s)}" for s in STYLES]
    return "\n\n---\n\n".join(parts)


def compose_context(style: str) -> str:
    return "\n\n---\n\n".join([read("engine.md"), read("reel-craft.md"), style_skill(style)])


def listing() -> str:
    names = sorted(p.relative_to(config.SKILLS_DIR).as_posix() for p in config.SKILLS_DIR.rglob("*")
                   if p.is_file() and p.suffix in (".md", ".html"))
    return "\n".join(names)
