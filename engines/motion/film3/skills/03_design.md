# Design: plain, precise HTML/CSS that looks like the product

## Use the product's own design language
Take the site's design system and use it exactly:
- colours, fonts, radii, borders, shadows
- button, card and input styles
- light or dark, dense or airy

Every surface must look like a screenshot of the real app, rebuilt cleanly. Never invent a generic dashboard.

## What makes UI look real
- **Content:** specific names, IDs, times and amounts that add up, the same across the film.
- **Hierarchy:** one title, secondary text in a muted colour, small uppercase labels with letter-spacing .06em.
- **Rhythm:** spacing on a 4/8 px grid with aligned edges. Use flex/grid with `gap`.
- **Status:** chips that carry meaning (green = done or paid, orange = pending, red = failed).
- **Icons:** simple inline SVG (stroke 1.6–2 px, round caps). No icon fonts, no emoji.
- **Borders:** 1 px, subtle (rgba of the text colour at 6–12%).
- **Shadows:** soft and layered: `0 1px 2px rgba(0,0,0,.08), 0 12px 32px rgba(0,0,0,.12)`.
- **Accent:** one accent colour, used only for what matters (the primary button, the key number, the live dot).
- **Numbers:** tabular (`font-variant-numeric: tabular-nums`).

## What makes it fake (forbidden)
- lorem ipsum or "Item 1"
- round numbers everywhere
- everything the same size
- rainbow colours
- huge radii on everything
- centred text in lists
- emoji
- gradients used only as decoration
- glassmorphism everywhere
- drop shadows on text inside UI
- fake charts with random bars

## Scale for film (viewers watch on phones)
- The frame is 1920×1080.
- Body text is ≥ 16 px at camera scale 1, and ≥ 20 px is better. Titles are 24–48 px. Hero numbers are
  64–200 px.
- The camera magnifies the subject: with camera scale 1.4, 16 px reads as 22 px.
- Show fewer items, and make them bigger. A list shows 3–5 rows, not 12.
- Each state is designed at its own final size (w×h in the carrier's shape table) and fills it. Leave no big empty areas, but
  keep 20–32 px of inner padding.

## Never rebuild the marketing website
The film shows the PRODUCT in use (its app, its messages, its dashboard, the device it lives on), never the company's
website: no site navbars, hero sections, "Products / FAQ / Log in" menus, cookie banners, footers or pricing pages.
The stage is where the product is used: a phone, a desktop, a laptop, a counter, a code-drawn space in the brand colour.

## Composition
- One focal point per state. Everything else supports it or is dimmed.
- The carrier is the subject. The stage around it is context: quieter, less saturated, blurred or dimmed.
- Light UI reads best on dark stages, and dark UI on light stages.
- Kinetic words need clear space: design the stage so there is calm room above or below the carrier.

## The end
The carrier becomes the brand's mark:
- the real logo file when it is given (`<img src="marks/…">`, ≥ 360 px wide or ≥ 160 px tall), otherwise the wordmark
  in the brand font at 110–160 px
- one line (the promise)
- the URL, in the muted colour

Keep it large, calm and centred.
