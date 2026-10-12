# 179. Đại Quản Gia Là Ma Hoàng ch 51-60 + STORY.md

Cùng cách làm như 177/178, từ `ep51..ep60/script.json`. Short M/N/O (ch 51-53 / 54-57 / 58-60: 48.5s / 47.4s / 45.4s, job 278/279/277) và hai Long chia đôi: ch 51-55 (8:58, job 280), ch 56-60 (11:10, job 281). Final QA 100.

Commit: "feat: manhua-series -- Dai Quan Gia ch51-60 + STORY.md".

- Long 51-60 một khối (199 beat, project 222) fail GENERATING_VOICE 4 lần ("No audio was received"), nên tách đôi như Long02/03; project 222 đổi tên "[FAILED - voice error, bỏ]".
- Thêm `STORY.md` + `build_story.py` trong thư mục series: cốt truyện từng tập (lấy từ lời kể các Long, bỏ bình luận) để làm tài liệu viết truyện; thêm Long mới vào `LONGS` rồi chạy lại.
