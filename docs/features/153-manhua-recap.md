# 153 — Manhua recap: `word_pop` captions, 2 built-ins, panel-recap tool

**Commit:** `37dc5b1`

The user brought a sample Vietnamese manhua recap Short and asked for tooling to make
two channels in that format. Analysis of the sample (ffprobe, scene detection, per-second
frames, whisper transcript) found: 47s at 9:16, a comic panel on screen every 1.5–2.5s
with zoom/pan, a male AI voice reading a gapless third-person recap at about 335
syllables/min, and one upper-cased, differently coloured word on screen at a time.

- **`word_pop` caption preset** in both render paths (`caption/ass_writer.py`,
  `video_composer/subtitles.py`) plus the duplicated preset lists (beat, video_composer,
  composition enum, frontend). One word per card, cycling colour palette, thick outline.
  The colour is chosen by segment index, not at random, so a re-render gives byte-identical
  ASS and the caption cache fingerprint stays valid. `segmentation._merge_orphan_chunks`
  skips merging when `max_words<=1`, because at that setting every card is a single word
  on purpose.
- **Built-ins `manhua_recap_vi`** (the comic's own panels, library mode) **and
  `manhua_ai_vi`** (an original story with a manhua `image_style_prompt`, run through
  "Generate Full by AI"). Both use the same captions and the same voice config
  (`vi-VN-NamMinhNeural` at 1.25 with a 0.1s pause). `manhua_ai_vi` stays in `library`
  mode like the other built-ins, because the create button decides the mode, not the
  template.
- **Vision input** for `llm_client.call_structured(images=[LLMImage...])`, supporting both
  providers. Each image gets a text label placed before it (e.g. "Panel 3"). OpenAI uses
  `detail="auto"`, because `low` can't read speech bubbles.
- **`POST /manhua-recap/script`** (`endpoints/manhua_recap.py`) takes panel paths and
  returns a title plus beats, where each beat is a strictly increasing panel number and
  one narration line. On a validation failure it retries once with the error added to
  the prompt.
- **`tools/manhua_recap/recap.py`** runs in three steps: `cut` (stack the pages, split on
  flat-colour gutter rows, so a panel split across two page images is still one panel),
  `script`, and `build` (register the panels as assets and create the project, following
  the same pattern as `bf.py`).

Verified: a synthetic 3-page chapter (8 panels, with page breaks falling mid-panel) was cut
into exactly 8 panels. A real OpenAI vision call on those 8 panels returned a valid
8-beat script in 12s. `word_pop` ASS burned through ffmpeg/libass rendered Vietnamese
diacritics correctly. Not yet run end to end through a factory render, because the
running backend predates this code.

**Follow-up (real chapter, manhuavn2.com Vạn Cổ Chí Tôn ch.2, 18 pages).** The first cut
merged bubble-linked panels into one strip 6823px tall. Over-tall segments (taller than
2x their width) are now split again at their emptiest row band. That run produced 56
panels, all within the limit. The first real script ran long: 44 beats / 533 syllables,
about 97s against a 50s target. The prompt now states a beat count (~target/2s) and the
validator sends a script over 1.3x the syllable budget back through the repair retry.
The re-run gave 25 beats / 338 syllables in a single call (~44k input tokens). The prompt
also tells the model to skip promo banners. Added `recap.py fetch <chapter url>`
(manhuavn2 only, plain public image URLs, refuses VIP-locked chapters).

**First full render (project 112, same chapter).** Final QA passed at 100. Quality Gate
raised warnings only: `LOW_RESOLUTION_ASSET`, because the source pages are 750px wide,
and a long run of BUILD beats. At voice speed 1.25 the render was 64.9s against a 48s
estimate, with measured narration of about 242 syllables/min versus about 335 in the
sample. Raising the speed to 1.6 gave 51.1s at about 308/min, and a whisper transcript of
the result was still clean. The template now uses 1.6, and the pace constant was changed
to 5.1 syllables/s. The script writer now assigns each beat's `type`
(SETUP/BUILD/REVEAL/REACTION), so the tool no longer marks every middle beat as BUILD.
`recap.py` reads `MANHUA_API` to target a backend other than :8000.

**Host commentary (for YouTube's reused-content policy).** The policy was re-read on
2026-09-25 (monetization policies, updated 2025-07-15). It rejects videos that "exclusively
feature readings of other materials" but allows "edited footage … where you add a storyline
and commentary". `POST /manhua-recap/script` now defaults to `commentary=true`. Beats are
tagged `kind: recap|commentary`, and the validator requires at least 2 commentary beats,
with the last beat being commentary and commentary making up at least 15% of the syllables.
The prompt splits the length budget roughly 75/25, because the first real run added the
host's take on top of a full-length recap and went over the maximum even after the retry.
On the real chapter the result was 26 beats, 7 of them commentary, and project 113
rendered at 58.6s with Final QA PASS 100. `recap.py script --no-commentary` gives the old
plain recap.

**Fix: edge_tts retry could hang forever.** Factory run 130 stayed in GENERATING_VOICE for
10+ minutes. After one NoAudioReceived, the retry's WebSocket stream neither yielded nor
closed, and there was no timeout. Each segment attempt is now wrapped in
`asyncio.wait_for(45s)` (`voice/providers.py`), so a stalled attempt counts as a failed
try. Covered by `tests/modules/voice/test_edge_provider_timeout.py`. This affects every
edge_tts project, not only manhua.

**Known gap:** BGM auto-selection has no wuxia-style track in the library, so project 112
got `horror.mp3` and 113 got a prayer track. Manhua-specific tracks still need to be
added.
