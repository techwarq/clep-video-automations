# The essence of the reference films: what made them good

Four hand-built films are the bar. You will not see their code. These are the decisions that made them work. Take
the decisions, never their products, worlds or words.

## What each one got right
**The messaging film (verified business messages, 43 s)** <!-- ref:truecaller -->
- It is about what the product CHANGES (messages you can trust), not about the phone. The phone is only the
  opening world.
- Chaos first: 24 anonymous notifications arrive with the gaps shrinking from 0.6 s to 0.15 s, an unread count
  climbs, and the viewer FEELS the problem before any claim.
- A swipe clears everything except ONE message, which glides to the centre. The camera pushes into it, and on the
  drop it BECOMES the product (same object, now verified).
- That one card morphs through five real use cases. In each one something is DONE: OTP copied, order steps light
  up, bill paid, seat assigned, stars filled. These are actions, not screens.
- It ends on scale: the card becomes one row among many, everything collapses into a counting proof number, then
  the name.

**The notch film (a Mac notch utility, 20 s)** <!-- ref:notch -->
- One object only: the notch. It never leaves; it morphs into a calendar alert, a file shelf and a battery
  activity.
- The product's magic is shown as physics: a file dragged from the desktop flies on an arc into its slot inside
  the notch. It is the same object all the way.
- The camera goes INSIDE the notch, and at the end the notch seen from inside becomes the mark.
- A quiet real context (menu bar, one window, wallpaper) makes the small object feel huge by contrast.

**The developer-infrastructure film (persistent agent machines, 30 s)** <!-- ref:maritime -->
- The interface metaphor drives every transition: the cursor stretches into a command bar, the bar grows into a
  terminal, the terminal shrinks into a tile, and the tiles pull back to become the halftone ocean (the brand's
  world).
- It tells time instead of claiming it: a day counter, the machine asleep, then silence (black, one dot), then a
  wake, and the SAME terminal is restored. "Same disk." The proof is the continuity itself.
- The logo is built from the film's own particles, which scatter and converge into the mark.

**The logistics film (trucking dispatch, 35 s)** <!-- ref:truemile -->
- The carrier is the product's smallest true thing: the truck's dot on a route map. It stops, becomes a pill,
  then a card, then opens into full-bleed footage through a headlight-shaped reveal.
- Information has weight: alerts are absorbed into a panel header along arcs, a glass lens opens a portal to the
  aerial view, a load is dragged on a board, and an approval goes out on a phone.
- It ends where the value lands in the world: an iris into the truck rolling out.

## The principles they share
1. **Understand, then find the carrier.** One object that carries the product's value through the whole film
   (a message, the notch, a cursor, a dot). Everything else is its world.
2. **A chain of events, each causing the next.** Problem felt, then the one thing, then used for real, then
   scale, then name. Never a feature list.
3. **Every transition is a transformation.** The same element changes shape, size and role (dot → pill → card →
   world). The camera scales through, and things fly on arcs into their new place. Zero cuts.
4. **Show, don't claim.** A number counting, a step lighting up, a file landing, a machine waking, rather than a
   sentence saying it.
5. **The payoff lands on the music's drop**, with the music muted for ½ beat before it.
6. **The subject is big:** 60–80% of the frame width. When the product UI is small, scale its whole world (×1.3)
   or push the camera in. The context stays dim, blurred or small.
7. **Nothing is ever frozen:** a slow world drift, a slow camera push of about 1%/s, beat pulses after the drop,
   and secondary motion (a counter, a progress bar) in every hold.
8. **The product's real UI**, rebuilt in HTML/CSS at film size: real-looking data (names, amounts, times), the
   brand's exact colours and font. Never a website screenshot, never generic boxes.
9. **Words are punctuation:** 2–5 words, one idea at a time, 78–130 px, in their own clear space (beside or
   above the subject, never on it). "Cut" style (scale-in in 0.12 s) for energy, rise style (0.34 s, outExpo)
   for calm.
10. **The ending is earned:** proof (a number or scale), a tagline, the real logo, the product name, the URL, each
    0.3–0.35 s apart. The logo, when possible, is made from the film's own material.

## Numbers that read as premium
- **Morphs:** 0.5 s, inOutCubic; arrival on the drop with outBack(1.1).
- **Content inside a morphing carrier** cross-reveals over 0.24 s: opacity, scale 0.95 → 1, blur 8 → 0. It
  leaves faster (0.8×, inCubic).
- **Camera:** scale moves in log space (`exp(lerp(log a, log b, p))`). A focus point is moved to a frame point.
  A push is ×2–2.3 into the subject, then ×1.3 more in 0.5 s as the old world blurs out.
- **Crowds:** arrivals accelerate, and each pushes the stack about 90–130 px over 0.3 s outCubic. A clearing
  gesture staggers 12 ms per item, inCubic, with blur.
- **Taps:** a touch dot approaches over 0.45 s, presses (scale 0.82), and a ripple spreads over 0.4 s. The UI
  answers within 50 ms (a label changes to its done state, a colour fills).
- **Staggers** on 8ths, and acts on downbeats. Stars fill 75 ms apart with a spring; steps light 150 ms apart.

## Code gotchas already paid for
- core.js `$` is getElementById; write a local `$`/`css`/`show`.
- `show()` must not clear an inline `display:flex`.
- Canvas arc radius must be ≥ 0. Await fonts and images in boot.
- A counter whose digit count changes makes the layout jump (a hard cut). Count to a number with a fixed digit
  count, or fix its width.
- Full-width text boxes that are scaled up run off the frame. Centre them with flex and scale the inner span.
- Declare `window.EVENTS = [[t, "kind"], …]` for every visible action, so each one gets a sound.
