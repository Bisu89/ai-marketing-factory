# TEMPLATE — produce an episode on the existing Vox Documentary engine (no new Remotion code)

> **Supersedes the build plan in [`PILOT.md`](PILOT.md) §6 and §8/§10** (not the research/script work —
> §1-5 of `PILOT.md` and all of [`CHANNEL.md`](CHANNEL.md)/[`STRATEGY.md`](STRATEGY.md)/
> [`SYNTHESIS.md`](SYNTHESIS.md) still stand). Decision made 2026-10-15: instead of building a bespoke 4th
> Remotion theme (`flatvector`/`explainer.tsx`) and two new components (`MechanismCutaway`, `HubDiagram`),
> this niche is produced on the **existing** `collage` theme, using 3 capabilities just added to it
> (`docs/documentary/PORTING_NOTES.md`, feature 188): the `TacticalMap` preset, the `ambient` particle
> overlay (rain/snow/wind/embers), and synthesized scene-cut SFX. **Zero new Remotion/backend code
> required to start producing episodes.**

---

## 1. The trade-off, stated plainly

| | Original plan (`PILOT.md`) | This template |
|---|---|---|
| Visual theme | New `flatvector` theme: thick black outlines, flat colour, no paper texture | Existing `collage` theme: kraft paper, torn-edge cards, tape — **AI images inside the cards stay flat-vector** (§2 below), only the *frame* around them is collage |
| New code needed | 1 theme file + `MechanismCutaway` (+ `HubDiagram` deferred) | None |
| "Hub, one thing does N jobs" beat | `HubDiagram` (bespoke, radiating spokes) | `EvidenceBoard` (existing — pinned cards + lines; **honest compromise**, see §3 beat 6 |
| "Cutaway, what's inside X" beat | `MechanismCutaway` (bespoke, animated reveal) | `SplitComparison` (existing — two static cards, "surface" vs "inside"; **not an animated reveal**, see §3 beat 9 |
| Sequence of named places | not planned | `TacticalMap` — **actually fits well**, see §3 |
| Atmosphere (snow/wind/rain) | would have been hand-drawn in the new theme | `ambient` overlay — direct fit, see §4 |
| Transition/dramatic-beat sound | not planned at all | synthesized SFX — direct fit, see §4 |

**Be honest with yourself when reviewing the first real episode**: the hub and cutaway beats are the
niche's *most distinctive* visual devices (`CHANNEL.md` §4 calls the hub "the most reliable device" and
appears in 3/3 reference videos). `EvidenceBoard`/`SplitComparison` are reasonable, zero-cost stand-ins,
not equivalent replacements. If they read as flat/unconvincing once you see a real cut, building the
original `MechanismCutaway`/`HubDiagram` spec (still fully written, `PILOT.md` §6.1/§6.2, nothing lost by
waiting) is still the right move — exactly the "don't build until proven needed" rule this project has
used throughout. This template exists so you can test that *before* spending that effort, not instead of
ever spending it.

---

## 2. Visual style (unchanged from `STRATEGY.md` §7)

AI images stay **flat-vector** (thick uniform outline, flat colour, no gradient, no texture) exactly as
speced in `STRATEGY.md` §7 and the prompt block already written in chat 2026-10-15. Write it once into
this folder as `IMAGE_STYLE.md` (mirroring `vox_documentary_template/IMAGE_STYLE.md`'s pattern — a fixed
prompt block + colour table, pasted verbatim into every image prompt) before generating any real image —
not done yet, do this first.

The `collage` theme's paper/tape/kraft framing goes *around* that flat-vector image, the same way
Biblical Figures already puts poster-collage artwork inside the same paper-card frames (`RULES.md` §8.5).
Nothing about the collage theme forces a particular image style; it only frames whatever `imageSrc` you
assign.

Colour-coding (`STRATEGY.md` §7's fixed palette: red-orange=heat, blue=cold/water, yellow=energy,
grey=neutral material) applies to **your image prompts and to `ambient`/SFX choices** (§4), not to
anything in Documentary's own code — there's nothing to configure for it.

---

## 3. The 10-beat script → existing preset mapping

Reuses the beat structure from `STRATEGY.md` §5.4 unchanged. One row per beat, with the honest fit
rating.

| Beat | Preset | Fit | Why |
|---|---|---|---|
| 1. Hook (concrete scene + paradox) | `PhotoKenBurns` | Good | Exactly its job: one image, slow pan/zoom, caption |
| 2. Promise ("this is the story of...") | `HeadlineImpact` or continue `PhotoKenBurns` | Good | Short punchy line; use `HeadlineImpact` only if it needs to stand alone from the hook image |
| 3. Flip the assumption | `SplitComparison` | **Good** | Literally "what you think (left) vs what's true (right)" — closer to this beat's job than to beat 9's |
| 4. Central principle + concrete number | `BigNumber` (for a real figure, e.g. "0.03 W/(m·K)") or `EvidenceBoard` (for a prose explanation) | Good | `BigNumber` already does the count-up/unit-label pattern; use it whenever the principle has a real measured number |
| 5. Sub-solution blocks (×1-3) | `PhotoKenBurns` / `NewspaperStack` | Good | Mechanism-by-mechanism beats are still mostly "image + caption" |
| 6. Hub (one thing, N jobs) | `EvidenceBoard` | **Compromise** | Draws N pinned labelled cards connected by lines — reads as "related facts," not naturally as "radiating from one object." Relabel the cards as the N jobs and accept the imperfect read, or skip this beat's visual flourish for the pilot and just say it in narration |
| 7. Convergent culture (optional) | `TacticalMap` | **Good** | This is the one beat `TacticalMap` was *not* originally built for but fits best: multiple named, unconnected places (Tuareg/Bedouin/Central Asia) each marked with a labelled block. Ignore the arrows' "movement" connotation, or narrate it as "the same answer, independently" rather than "a journey between them" |
| 8. Transition to summary | (no preset — a narration-only beat) | — | SFX "stinger" cue here (§4) substitutes for a visual device |
| 9. Recap | `HeadlineImpact` (one line per recap point, in sequence) | OK | |
| 9b. (if the topic needs a literal cutaway, e.g. the Inuit pilot's S06 "inside a block of snow") | `SplitComparison` | **Weak, flagged** | Left card = whole object photo, right card = a *second, separately-generated* close-up/cutaway illustration. Static, not an animated reveal. This is the one beat where the gap from §1's table is real — see the decision note there |
| 10. Outro callback + closing line | `PhotoKenBurns` (callback to the hook's own image) + `HeadlineImpact` (closing line) | Good | |

---

## 4. Ambient + SFX production guidance

Both are **manual, per-scene, opt-in** — nothing here is automatic (`PORTING_NOTES.md` parts A/C).

| Climate / moment | `Scene.ambient` | SFX hint text to type in Storyboard (`sfx_cues`) | Maps to style |
|---|---|---|---|
| Arctic/snow episodes (hook, atmosphere scenes) | `snow` | "gió lướt" / "wind" | `whoosh` or `wind` |
| Desert episodes | `wind` | "gió", "nóng" | `wind` |
| Rain/monsoon episodes (e.g. Dutch sea-level idea, `STRATEGY.md` §6.2 item 6) | `rain` | "mưa", "nước" | `wind`/`whoosh` (no dedicated rain SFX catalog entry yet — `sfx.py` only has whoosh/impact/stinger/wind, see `PORTING_NOTES.md` part A) |
| Beat 3 "flip the assumption" reveal, beat 8 transition | — (no ambient) | "kịch tính", "bất ngờ" | `stinger` |
| Any hard cut you want punctuated | — | "va đập", "bùm" | `impact` |

Render tab: tick **"Bật hiệu ứng âm thanh theo cảnh"**, leave the dB default (-14) for the pilot. Leave
`ambient` empty on every scene except the ones in the table — it's full-bleed and reads best used
sparingly (1-2 scenes per episode), not on every scene.

---

## 5. Worked example: the Inuit pilot's 6 scenes, remapped

Re-reads `PILOT.md` §5 (the already-written storyboard + narration, unchanged) against this template —
no new writing needed for S01-S05, only S06 changes:

| Scene | `PILOT.md`'s plan | This template |
|---|---|---|
| S01 Hunter on sea ice | `PhotoKenBurns` (as planned) | same — add `ambient: "snow"` + SFX hint "gió lướt" (`wind`) for atmosphere |
| S02 Cutting blocks | `PhotoKenBurns` (as planned) | same, no ambient (close-up, wind less relevant) |
| S03 Dome + paradox line | `PhotoKenBurns` + text overlay (as planned) | same |
| S04 Map: Canada's Central Arctic | `MapZoom` (as planned, needs a real map image) | same — **unchanged by this template**, still needs a real map image, `TacticalMap` does not help a single-point "where is this" scene |
| S05 Thesis statement | `HeadlineImpact` (as planned) | same |
| S06 Cutaway: inside a block of snow | **`MechanismCutaway`, new component** (as planned) | `SplitComparison`: left = the snow dome exterior (reuse S03's image), right = a new AI image "cutaway illustration of a snow block cross-section, trapped air pockets between ice crystals, flat vector diagram style, labelled" — **static, not a reveal animation; the honest gap from §1** |

Net result: **this pilot now needs zero new Remotion code** to render end to end on the existing
`collage` theme. The only real open item is whether S06's static split-comparison communicates "trapped
air" as well as an animated cutaway would — judge that from the actual render, not in the abstract (same
"test the 45-60s segment before committing" discipline `PILOT.md` §9.2 already set out).

---

## 6. Next action

Render the Inuit pilot's 6 scenes (§5) for real through this template: write `IMAGE_STYLE.md` (§2), get
6 real flat-vector images (S01-S03 narrative scenes, S04 a real map image, S05 none needed, S06 two
images), build the manifest through the actual Documentary project flow this time (not a hand-rolled
Remotion-only test), and look at the real result — especially S06 — before deciding whether the
`SplitComparison` compromise holds up or `MechanismCutaway` needs building after all.
