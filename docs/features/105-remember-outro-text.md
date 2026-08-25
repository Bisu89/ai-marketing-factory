# 105. Remember Ending Text (Outro) Across Modal Opens

**Commit:** _pending_

Real user request: "Ending text (outro, optional)" should also be
remembered when reopening New Video, the same as Template and Content
language already are — a channel usually reuses the same CTA line
("Theo dõi để xem phần 2 nhé!") across most/all of its videos.

## What changed

`NewVideoModal.tsx`: added `LAST_OUTRO_TEXT_KEY` ("nvm:lastOutroText"),
following the exact same read-on-open/write-on-change localStorage
pattern already established for `LAST_TEMPLATE_ID_KEY`/
`LAST_CONTENT_LANGUAGE_KEY`. Deliberately not applied to
`aiMetadataEnabled`/`autoProduce` (those stay per-video decisions, not
reused copy).

## Verification

`npx tsc -b --noEmit` clean. Real browser check: typed an outro line into
the field, closed the modal, reopened it, confirmed the exact same text
was still there.
