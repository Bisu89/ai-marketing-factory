# 190 — Packed Light ep1 opening test cut (pictures + voice + SFX)

A ~61s test of the PACKED LIGHT opening (campground, tarp, the stove argument, wet wood, first failed match), built from 12 AI pictures + camera moves + light fx, three edge-tts voices (narrator/dad/son), synthesized SFX and a soft pad. Composition `PkOpen` in `remotion/`. Purpose: judge whether this look holds attention, after the vector stick-figure test (189) read as too flat.

Commit: `feat(remotion): Packed Light ep1 opening test cut (PkOpen) + generators`

Key files: `content-prompts/packed_light/ep01_open_test.csv` (shot list + image prompts; pictures themselves are not committed), `remotion/src/pk-ep01/{Open,PkKenBurns}.tsx`, `remotion/src/pk-ep01/data.ts` (generated), `tools/packed_light/{prep_images,gen_voice_timeline,gen_sfx}.py`.

Decisions:
- Timeline is generated from the real voice-line durations, so shot lengths follow the audio, not the CSV's word-count estimate (CSV said ~52s, real cut is 61s).
- `PkKenBurns` is a trimmed port of stickman-video's `zs-ep01/KenBurns.tsx` (zoom/pan, sway, fog, dust, wind, glow) rather than a copy of it plus `Fx.tsx`, to avoid dragging the zombie series' HUD/cards along.
- SFX/music are numpy-only (no scipy): this machine's Python has no scipy and installing it would touch the backend venv. Media (`remotion/public/`, `out/`) is git-ignored.
- Pictures are upscaled 1672x941 -> 1920x1080 (lanczos) before rendering.

Checked: tsc clean; stills and frames extracted from the real mp4 viewed; ffprobe 1920x1080 / 30fps / 1833 frames / AAC, peak -5.7 dB. Caught: notice-board text overflowed the board (font shrunk), a first generator patch silently failed (re-verified by confirming `data.ts` was really rewritten). Not verified: motion feel and audio mix by ear.
