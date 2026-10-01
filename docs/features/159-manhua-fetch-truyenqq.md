# 159. truyenqq.com.vn fetch support

Added as a fourth supported site for the manhua chapter fetch (feature
154 / 158), after `zettruyen2.com` turned out to be rate-limited during
diagnosis of 158 and the user wanted a working alternative. Unlike
zettruyen, `truyenqq.com.vn` is a plain HTTP(S) fetch -- no Cloudflare
reset, no headless browser needed.

URL shape: `truyenqq.com.vn/<slug>/chapter-N` (no `truyen-tranh/`
segment). Page images are `<img data-src="https://sN.cc3t.net/chapters/...">`;
that CDN also 403s without a `Referer`, same pattern as the other sites.

Verified end-to-end: `fetch_chapters()` against a real chapter saved 14
pages, 0 skipped. `tests/api/test_manhua_recap.py` (11 tests) passes
unchanged.

Key files: `backend/app/modules/manhua/fetch.py` (new `elif "truyenqq"`
branch in `_chapter_page_urls`), `backend/app/api/v1/endpoints/manhua_recap.py`
and `frontend/src/pages/ManhuaFetchPage.tsx` (help text),
`tools/manhua_recap/recap.py` (docstring).
