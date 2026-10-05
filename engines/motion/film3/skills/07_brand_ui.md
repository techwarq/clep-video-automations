# Brand UI: study the real product, then rebuild it exactly

A film looks like the brand only if its UI is the brand's REAL UI. Before any story is written, study every
picture of the actual product: site mockups, App Store screenshots and the user's uploads. Then write down how
it is built.

## 1. Understand the product first; the picture follows from it (NOT from a device)
Read the website like a strategist: what problem exists in the world without this product, what happens when it
works, what OBJECTS carry that change (messages, parcels, invoices, calls, code, agents, money, data, people, places),
and what the product's own UI pieces are. The film draws THOSE elements in a designed space.

- A device (phone, laptop, browser) appears ONLY if the story is literally "someone using the app" at that moment,
  and even then briefly — as one act, not the whole film. Most films should live in a designed brand world where the
  product's objects and UI pieces float, stack, flow, connect and transform at film scale.
- Never put the whole film on a phone (or in a browser) just because the product is an app. Example: a delivery
  platform is about PARCELS and promises kept — so the film is about a parcel's journey, the exception that gets
  caught, the customer message that answers itself, the on-time number; the driver's phone is at most one moment.
- Ask: what would a great motion studio draw to explain this in 30 s without words? Draw that.

## 2. Find the real surfaces
- In the images, find the regions that show the PRODUCT's UI, not the marketing site around it. Examples: a chat
  screen inside a phone mockup, a notification card, a dashboard panel, a pricing sheet inside the app.
- Give each one a tight box, as fractions 0–1 of the image: [x0, y0, x1, y1].
- Name each surface the way the product would ("business chat notification", "chat thread",
  "verified business header", "invoice screen").
- **Ignore:** the site's navbar, hero headline, cookie banners, stock photos of people, and other apps' UI.

## 3. Write the UI spec (as a builder would need it)
For each surface, describe its anatomy from top to bottom:
- header (height, colour, what sits left and right)
- rows and bubbles (radius, padding, background, border)
- badges (shape, colour, text case)
- buttons (filled or text links, colour, radius)
- type (sizes relative to each other, weights, case)
- icons (outline or filled, size)
- spacing rhythm
- signature details that make it recognisable, such as a coloured border on a notification, a verified tick
  next to a name, or a coloured status strip

Colours come from the measured palette you are given. Use those hex values and never invent new ones.

## 4. Rebuild rule for every state
When a state shows one of these surfaces, rebuild it EXACTLY:
- the same anatomy, colours, radii, badge shapes and button styles
- the product's own copy style

Change only the data, to the film's demo scenario. A viewer who uses the product must recognise it
instantly. A generic card with the brand's colour is a failure.
