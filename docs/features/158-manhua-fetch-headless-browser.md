# 158. zettruyen*.com fetch via headless browser

`zettruyen2.com` sits behind Cloudflare and was resetting the raw TLS
connection for every non-browser client -- plain `urllib`, `curl`, and even
`curl_cffi` impersonating Chrome's TLS fingerprint all got the same reset,
while a real browser worked fine. So the "tải chương" menu (feature 154)
and the CLI's `fetch` command failed for this site even though the chapter
URL itself was fine.

Fix: `_chapter_page_urls` in `app/modules/manhua/fetch.py` now loads the
chapter HTML through a real headless Chromium (Playwright) for
`BROWSER_ONLY_SITES` (currently just `zettruyen`), instead of a plain GET.
The page image CDN downloads themselves are untouched (still plain
`urllib` with a `Referer` header) -- only the HTML listing page needed the
real browser. `manhuavn2.com` and `cotruyenday.com` are unaffected.

Requires a one-time `python -m playwright install chromium` in the backend
venv (not run automatically). Added `playwright==1.62.0` to
`requirements.txt`.

Not yet verified against the live site end-to-end: repeated test requests
during diagnosis likely tripped Cloudflare's own rate-limiting for that IP,
so the headless-browser path also got reset in testing. The existing
`tests/api/test_manhua_recap.py` suite (11 tests) passes unchanged.

Key files: `backend/app/modules/manhua/fetch.py`,
`backend/requirements.txt`.
