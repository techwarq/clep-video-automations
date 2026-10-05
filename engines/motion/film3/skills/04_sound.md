# Sound: music first, every action has a sound, silence before the hit

## Music
- Pick a track from the library whose character matches the brand's energy. The film is built on its bars.
- The film's bars are the track's bars. You choose which sections of the track to use (`sections`: source bar
  ranges, joined at bar boundaries). Use this to reach the right length, or to put the drop where the payoff is.
- Put the biggest reveal (payoff or finale) on the drop bar. Build toward it with rising density: faster morphs
  and shorter holds.
- Mute the music for ½ beat right before the drop (`"mute": [[drop − ½ beat, ½ beat]]`). The hit then lands out
  of silence. If you forget, the sound pass adds it.

## The palette (map kinds to library ids)
Each film chooses its own palette from the SFX library, and it must match the world. Warm films get soft,
organic sounds (felt clicks, paper, wood). Technical films get dry, precise digital sounds (blips, ticks,
servo moves).

| kind | used for |
|---|---|
| `morph` | the carrier changes shape (a soft swoosh or stretch) |
| `bloom` | the carrier grows into something bigger (a stretch or riser-ish swell) |
| `collapse` | the carrier shrinks back (a short collapse) |
| `click` | cursor clicks and taps |
| `type` | keystrokes (one cue per burst of typing) |
| `tick` | small arrivals, counters and staggers |
| `pop` | notifications and chips popping in |
| `whoosh` | camera pushes and pulls, and flights taking off |
| `drop` | a flight landing or an item dropped into place |
| `word` | a kinetic word appearing (quiet) |
| `impact` | the drop and big hits |
| `success` | a done, paid or verified moment |
| `logo` | the end sting |

## Rules
- Every visible action has a sound. Nothing is silent that moves big.
- Stack no more than 3 sounds at the same instant. Repeats vary their pitch: give each repeat a `rate`
  between 0.94 and 1.08 (the sound pass does this for the cues it adds).
- Keep levels quiet: clicks, ticks and words sit at −10 to −14 dB, morphs at −6 to −9 dB, impacts and the
  logo at −2 to −4 dB.

## Declare the events, and the gaps fill themselves
Put `window.EVENTS = [[t, "kind"], …]` in the film (kinds as in the table, plus `swipe`, `arrive`, `count`). At
render time, every event with no cue within 0.1 s gets a library sound from the film's palette (warm or cold, from
the track or `"palette"` in mix.json), the drop gets its hit and mute, and the end gets the logo sting. Write your
own cues for the moments that matter most, with pitch variety; the pass only fills gaps.
