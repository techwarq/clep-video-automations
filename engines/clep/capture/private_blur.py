from __future__ import annotations

import json

LAYER_SCRIPT = r"""
(() => {
  const selectors = __SELECTORS__;
  const any = () => true;
  const luhn = (text) => {
    const digits = text.replace(/\D/g, "");
    if (digits.length < 13 || digits.length > 19) return false;
    let sum = 0;
    for (let i = 0; i < digits.length; i++) {
      let d = +digits[digits.length - 1 - i];
      if (i % 2) { d *= 2; if (d > 9) d -= 9; }
      sum += d;
    }
    return sum % 10 === 0;
  };
  const patterns = [
    { re: /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, check: any },
    { re: /\b(?:sk|pk|rk|ghp|gho|ghs|xox[abpr]|AKIA|AIza)[A-Za-z0-9_\-]{10,}\b/g, check: any },
    { re: /\b(?:api|secret|token|key)[_-][A-Za-z0-9_\-]{12,}\b/gi, check: any },
    { re: /\b(?:\d[ -]?){13,19}\b/g, check: luhn },
  ];
  const matches = (text) => {
    const found = [];
    for (const { re, check } of patterns) {
      re.lastIndex = 0;
      for (let m = re.exec(text); m; m = re.exec(text)) if (check(m[0])) found.push(m);
    }
    return found;
  };
  let layer = null;
  const ensureLayer = () => {
    if (layer && layer.isConnected) return layer;
    layer = document.createElement("div");
    layer.setAttribute("data-clep-private-layer", "");
    layer.style.cssText = "position:fixed;inset:0;pointer-events:none;z-index:2147483647;";
    document.documentElement.appendChild(layer);
    return layer;
  };
  const rectsOfText = () => {
    const rects = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const text = node.nodeValue;
      if (!text || text.length < 6 || node.parentElement?.closest("[data-clep-private-layer]")) continue;
      for (const m of matches(text)) {
        const range = document.createRange();
        range.setStart(node, m.index);
        range.setEnd(node, m.index + m[0].length);
        rects.push(...range.getClientRects());
      }
    }
    return rects;
  };
  const rectsOfFields = () => {
    const rects = [];
    for (const field of document.querySelectorAll("input:not([type=password]):not([type=file]), textarea")) {
      const value = field.value || "";
      if (value.length >= 6 && matches(value).length) rects.push(field.getBoundingClientRect());
    }
    return rects;
  };
  const rectsOfSelectors = () => {
    const rects = [];
    for (const selector of selectors) {
      try { for (const el of document.querySelectorAll(selector)) rects.push(el.getBoundingClientRect()); } catch (e) {}
    }
    return rects;
  };
  const draw = () => {
    if (!document.body) return;
    const target = ensureLayer();
    const rects = [...rectsOfText(), ...rectsOfFields(), ...rectsOfSelectors()]
      .filter((r) => r.width > 1 && r.height > 1 && r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth);
    while (target.childElementCount > rects.length) target.lastElementChild.remove();
    while (target.childElementCount < rects.length) {
      const cover = document.createElement("div");
      cover.style.cssText = "position:fixed;border-radius:4px;backdrop-filter:blur(7px);-webkit-backdrop-filter:blur(7px);background:rgba(128,128,128,0.18);";
      target.appendChild(cover);
    }
    rects.forEach((r, i) => {
      const style = target.children[i].style;
      style.left = `${r.left - 3}px`; style.top = `${r.top - 2}px`;
      style.width = `${r.width + 6}px`; style.height = `${r.height + 4}px`;
    });
  };
  const start = () => {
    draw();
    new MutationObserver(draw).observe(document.documentElement, { subtree: true, childList: true, characterData: true });
    addEventListener("input", draw, true);
    addEventListener("scroll", draw, true);
    setInterval(draw, 120);
  };
  document.readyState === "loading" ? addEventListener("DOMContentLoaded", start) : start();
})();
"""


def install(context, selectors: list | None) -> None:
    wanted = [str(s) for s in (selectors or []) if isinstance(s, str) and s.strip()]
    context.add_init_script(LAYER_SCRIPT.replace("__SELECTORS__", json.dumps(wanted)))
