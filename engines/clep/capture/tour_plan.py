"""Where a tour stops on a page and how long it holds each stop."""
from __future__ import annotations


def section_hold(duration: float | None, n_stops: int, default: float = 2.4) -> float:
    """Seconds to hold each tour stop so the tour fits the requested runtime (about 2.5s goes to open and close)."""
    if duration and n_stops:
        return min(4.0, max(1.4, (duration - 2.5) / n_stops))
    return default


def ground_sections(requested: list[str], page_sections: list[dict],
                    limit: int = 6) -> list[dict]:
    """Map requested section words onto real page headings (fuzzy substring).

    Returns ordered stops: {heading, anchor, matched}. Unmatched requests
    are kept as caption-only stops so nothing the user asked for is dropped.
    Unknown pages (no headings found) fall back to the raw requests.
    """
    if not requested:
        return [{"heading": s.get("heading", ""), "anchor": s.get("anchor"),
                 "matched": True} for s in (page_sections or [])[:limit]]
    stops: list[dict] = []
    pool = list(page_sections or [])
    for req in requested:
        needle = req.lower()
        if needle.strip() in ("hero", "top", "intro", "header", "landing", "home"):
            stops.append({"heading": req, "anchor": None, "matched": True, "top": True, "asked": req})
            continue
        best = None
        for cand in pool:
            hay = f"{cand.get('heading','')} {cand.get('anchor','')} {cand.get('id','')}".lower()
            if needle in hay or any(w in hay for w in needle.split() if len(w) > 3):
                best = cand
                break
        if best is not None:
            pool.remove(best)
            stops.append({"heading": best.get("heading") or req, "anchor": best.get("anchor"),
                          "matched": True, "asked": req})
        else:
            stops.append({"heading": req, "anchor": None, "matched": False, "asked": req})
    # Too few real stops: fill with the page's own sections (in page order) so
    # the tour shows real content under real headings, never a guessed spot.
    real = sum(1 for s in stops if s["matched"] and not s.get("top"))
    for cand in pool:
        if real >= min(3, limit):
            break
        stops.append({"heading": cand.get("heading", ""), "anchor": cand.get("anchor"),
                      "matched": True, "filled": True})
        real += 1
    return stops
