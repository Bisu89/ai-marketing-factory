# 151 — Fix: Outro card crashed/blanked when its text had an apostrophe

**Commit:** `b95ded1`

## The bug

`app/modules/outro/renderer.py`'s `_escape_drawtext` escaped a literal `'`
as `\'` for embedding inside a single-quoted ffmpeg drawtext value. ffmpeg's
filtergraph parser has no such escape — `'` always toggles quote state,
backslash or not. Found for real rendering the new
[Zombie System](150-zombie-system-template.md) template's own default
outro text ("...subscribe so you don't miss it."):

- With the value quoted (`text='{prefix}'`) it crashed ffmpeg outright:
  `No such filter: '<some unrelated number>'` — the stray unbalanced quote
  shifted parsing of everything after it in the `filter_complex` string.
- A first fix attempt (backslash-escape `'` for an *unquoted* value
  instead) didn't crash, but silently broke rendering from that character
  on — confirmed by dumping the actual `filter_complex` string and
  bisecting rendered frames: the clip goes solid black the instant a
  `\'`-containing drawtext filter's `enable` window starts, because the
  same unbalanced-quote problem corrupts every filter after it in the
  comma-separated chain.

Every built-in template's outro text shipped so far (e.g.
`history_documentary`'s "If you made it this far, subscribe...") happens
to have no apostrophe, so this was latent until Zombie System's text hit
it.

## The fix

Normalize `'` to the typographic U+2019 (') instead of trying to escape
it — sidesteps ffmpeg's quote-toggle parsing entirely (and reads better on
screen than a straight quote). Every other drawtext value switched to
unquoted + fully backslash-escaped (`:`, `%`, `,`, `[`, `]`, `=`, `;`), so
no quote-balancing is needed across `_reveal_tokens`' per-character prefix
slicing for the typewriter reveal effect.

## Verification

`pytest -k outro` green (4 passed). Real fix confirmed two ways: (1) an
isolated `render_outro_clip()` call with the exact failing text, bisecting
frames before/after the fix; (2) the full Zombie System episode 1 factory
run end to end, spot-checking the final outro-card frame shows the
complete text correctly.

## Key files

- `backend/app/modules/outro/renderer.py` — `_escape_drawtext` + the two `drawtext` filter f-strings
