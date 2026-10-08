# 160. Manhua fetch: filler filter fixes

The "Tải chương truyện" filter (hash-based, feature 154) had two real
failures while downloading *Chàng Rể Mạnh Nhất Lịch Sử* ch.1-100:

- A site that serves every page twice (ch.89: 92 images, 47 distinct) lost
  both copies of each page -> only 2 pages kept. Now a page repeated inside
  one chapter keeps its first copy; the same image across different
  chapters in one run is still dropped everywhere.
- Re-fetching a chapter (even after deleting its folder) flagged every page
  as "already seen" -> 0 pages. The cache now remembers the chapter URLs
  each hash was seen in and only flags it when seen in a *different*
  chapter. Old count-only cache entries survive only at count >= 3 (clearly
  recurring), since a smaller count can't tell a re-fetch from an ad.

Logic lives in `_find_filler` (`backend/app/modules/manhua/fetch.py`),
tested in `backend/tests/modules/manhua/test_filler.py`. Verified on the
real ch.89 (45 saved) and a re-fetch of ch.1 (13 of 14 saved).

Not done: content-based ad detection (QR/promo text). OpenCV's QR detector
found none of the known header QR codes (too small) and `cv2` isn't a
declared dependency, so a first-time standalone ad page can still slip
through and must be deleted by hand.
