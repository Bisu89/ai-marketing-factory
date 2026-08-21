# 91. "Generate Full by AI" Remembers Template + Content Language

**Commit:** `c10c133`

Real user report: Template and Content language reset to the hardcoded
default (first template in the list, English) every time `NewVideoModal`
reopened, forcing a re-pick on every single video even for users who
pick the same one repeatedly.

Now persisted client-side (`localStorage` -- this modal has no per-user
account/profile concept to persist to server-side): read once when the
modal opens (falling back to the old defaults only if nothing was
remembered yet, or if the remembered template id no longer exists), and
written back whenever either changes. Content language driving Voice
Factory's narration language/provider is what "giọng đọc" (reading
voice) refers to here -- this modal has no separate voice dropdown of
its own.

Verified with real Playwright against the running app: opened the modal,
picked a non-default Template and Vietnamese, closed it, reopened it,
confirmed both selections were remembered.
