# Motion rules — STRICT (`check` measures most of them, for free)

Sources distilled: UX in Motion's 12 principles (easing, offset & delay, parenting, transformation, value change,
masking, overlay, cloning, obscuration, parallax, dimensionality, dolly & zoom), Material motion (container transform,
duration by size, emphasized easing), classic animation principles (anticipation, follow-through & overlap, arcs,
secondary action, staging, slow in / slow out), editing theory (match cut, eye-trace, cut on action) and the
hand-built reference films (notch, truecaller, truemile, maritime).

## A. NO HARD CUTS. The film is ONE continuous take.
1. There are no cuts. No dissolve between unrelated pictures, no fade to black and back, no wipes, no push/slide
   "slideshow" transitions, no scene that simply appears. The jump detector in `check` flags any frame that
   changes far more than the frames around it.
2. Every change of picture uses one of these continuity devices:
   a. **Container morph (transformation):** the same container changes x, y, w, h, radius and colour in one move.
      Old content leaves inside it and new content arrives inside it. This is the default.
   b. **Shared element (cloning / flight):** an element of picture A flies on an arc to its exact slot in picture B.
      The slot is hidden until the element lands, so it is the same object.
   c. **Scale-through (dolly & zoom):** the camera pushes into an element until it fills the frame. Its fill colour
      or its content becomes the next world.
   d. **Pull-back:** the camera pulls out to show that the object belongs to something bigger.
   e. **Masking reveal:** a new surface is revealed through a shape that grows from an existing object
      (a circle from a button, a rect from a row).
   f. **Value change:** a number, text, chart or status changes in place (counter, typing, bar growth, check).
   g. **Parenting:** children ride their parent's motion. When a card moves, its contents move with it.
3. **Match rule (eye-trace):** whatever the eye is on in the last frame of A is, in the first frame of B, at the same
   place, the same size (±15%) and the same colour (or already morphing toward the new colour).
4. In every frame, at least one large thing is the same object it was one frame ago.
5. Never fade the whole frame. The only full-frame solid colour allowed is inside a scale-through, where the frame
   is filled by the pushed element's own colour.
6. Kinetic words never replace the picture. They rise into clear space beside the carrier while it stays on screen.
7. The end card is the carrier's final morph, for example into the logo tile. It does not appear on its own.

## B. Timing, as rules for the graph editor
1. Ease everything. Linear motion is only for constant motion (drift, marquee, progress, loaders).
2. **Arrivals** ease out (fast start, long settle): `settle` or `snap`. **Blooms** (a container growing into a
   feature) use `bloom`, which overshoots slightly: anticipation plus follow-through.
3. **Moves between two resting states** use `glide` (in-out). Use ease-in (`push`) only for exits and for
   push-ins that accelerate into a hit.
4. **Duration by size:**
   - small (icon, badge, check): 0.10–0.20 s
   - medium (chip, button, row): 0.25–0.40 s
   - large (card, panel, window): 0.40–0.70 s
   - carrier morph: 1–2 beats
   - camera push or pull: 1–4 beats

   Nothing large ever moves in under 0.3 s.
5. **Offset & delay:** siblings never move together. Stagger them by an 8th or a 16th note (0.04–0.12 s) in
   reading order, or outward from the cause.
6. **Overlap (follow-through):** the next motion starts before the previous one has fully settled. Content starts
   revealing about 45% of the way through a container morph. Different properties settle at different times:
   position first, then scale, then blur.
7. **Holds:** a state holds long enough to read. That means ≥ 1 s for a short line and 1.5–2.5 s for UI with a
   number. Nothing sits frozen for more than 1.5 s; something inside must be moving (a counter, typing, a pulse,
   a progress bar, a live waveform).
8. **The beat grid:** arrivals and hits land on beats, small events on 8ths, typing on 16ths. The biggest reveal
   lands on the music's drop.
9. **Rhythm:** alternate the energy. A quick snap follows a slow glide. Put a hold and half a beat of silence
   before the biggest hit.
10. **Contrast between holds and moves:** a hold is calm (only the world drifts, plus one small live detail);
    a move is decisive (most of its travel in its first third, done in 0.3–0.6 s). If everything drifts a little
    all the time and no move is clearly bigger, the film reads floaty: `check` measures this. Text never drifts
    or slowly scales while it is being read; hold it still and move it as part of a move.
11. **One solid object through every change:** never cross-fade one screen into another at half opacity on top
    of each other (a double exposure). Morph the container and reveal the new contents inside it, or move the
    old screen away as the new one arrives. `check` flags screens cross-fading for 0.5 s or more.
12. **Use the engine's eases, not your own:** `E.outExpo` for moves (fast out, soft landing), `E.outBack` or `S()`
    springs for arrivals (a small overshoot is the bounce), `E.inOutCubic` only for long camera moves. Do not write
    your own easing function. Never sway UI or the camera with `Math.sin(t)`: a constant sub-pixel sway makes text
    shiver. `check` flags both.

## C. Space and camera
1. The camera is always alive: one slow eased push (under 1%/s) toward what changes, and pull-backs reveal
   context. It travels in one direction per beat; it never sways back and forth.
2. Camera scale moves in log space (`Math.exp(lerp(log a, log b, p))`), so zooms feel constant-speed.
3. Flights follow arcs, never straight lines. Arc height is 5–15% of the distance.
4. Keep a consistent direction: the story flows one way, and things exit toward where the next thing comes from.
5. The subject sits in the middle third and fills 55–80% of the frame width. Nothing important is small in empty
   space.
6. **Parallax:** the background moves less than the foreground. Context is dimmed or blurred.
7. Motion blur comes from the renderer's sub-frames. Never fake it with CSS blur on moving things.

## D. The reveal inside a morph
- **In:** opacity 0→1, blur 8→0 px, scale 0.94→1 over 0.22–0.3 s. Then children stagger in, each rising
  12–24 px and fading up, 1/16 apart.
- **Out:** faster (0.8×), ease-in, blur rising to 6–8 px. Reveal the whole state layer, then stagger its
  children.

## E. Secondary action (life)
While a state holds, give it one secondary motion that means something:
- a counter ticking
- a progress bar
- a typing caret
- a live dot pulsing on the beat
- a waveform
- a status flipping
- a row sliding in

Keep it to one or two at a time, never everything at once.

## F. Anti-slop (all forbidden)
- Everything bouncing (overshoot is only for blooms).
- Spinning or flipping logos.
- Random particles or sparkles.
- Glow on everything.
- Text flying in from the frame edges.
- 3D card flips for no reason.
- Every element moving at the same time.
- Shaky camera.
- Whole-frame flashes.
- Emoji.
- Gradients used only as decoration.
- "Loading…" spinners that stand for work: show the real work instead.

## G. Self-check before you answer
- Can you name, for every change, which device (A.2 a–g) carries the eye? If not, redesign that change.
- Does every state arrive on a beat, and is the drop the biggest moment?
- Is there anything tiny in empty space, text over busy UI, or a frame where everything is new? Fix it.
