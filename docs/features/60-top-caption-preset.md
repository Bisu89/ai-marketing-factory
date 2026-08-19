# 60 — "Top" Caption Preset

**Commit:** `TBD`

Found via a real user report: the 5 existing caption presets only ever
placed text at the bottom (`emotional`/`cinematic`/`word_highlight`) or
dead-center (`big_statement`/`quote`) -- no option sat near the top edge,
and `big_statement`'s large, center-screen text was specifically what the
user was complaining about.

Added a 6th preset, `top`: alignment 8 (ASS top-center), a modest 9% top
margin, and a smaller font scale (0.85x) than the default -- reuses the
same plain "static lines" layout `cinematic` already has, just
repositioned/resized. Updated in all 4 places this preset enum/tuple is
duplicated by this codebase's own module-boundary convention
(`beat/schemas.py`, `caption/ass_writer.py`, `video_composer/models.py` +
`service.py`, `composition/schemas.py`), plus the frontend mirror
(`types/videoFactory.ts`) -- the existing preset dropdown picks it up
automatically, no new UI needed.

Verified against real FFmpeg output (burned into an actual video) and
against the pre-computed Caption Engine's own `.ass` generation, both
produce the same `Alignment=8` style line.
