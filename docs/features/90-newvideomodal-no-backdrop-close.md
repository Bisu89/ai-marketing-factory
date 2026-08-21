# 90. Fix: "Generate Full by AI" Popup Closed on Outside Click

**Commit:** (pending)

Real user report: clicking outside `NewVideoModal` closed it and lost
everything typed (name/idea/script/outro text). Removed the backdrop's
`onClick={onClose}` -- the modal now only closes via its X button or
Cancel button.

Verified with real Playwright against the running app: typed a value,
clicked the backdrop, confirmed the modal stayed open and the value was
preserved; confirmed the X button still closes it.
