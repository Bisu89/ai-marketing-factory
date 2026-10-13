# 183. Đại Quản Gia Là Ma Hoàng ch 81-100: build 5 Long + 6 Short

Build từ `ep81..ep100/script.json` sau khi review/viết lại (xem 182; ep95-98 review thêm, ep99-100 viết mới vì chưa có script). Final QA 100 cả 11 video.

| Video | Chương | Độ dài | Project / job |
|---|---|---|---|
| Short V / W / X | 81-83 / 84-87 / 88-90 | 52.3s / 47.7s / 47.2s | 237-239 / 292, 293, 294 |
| Long | 81-85 | 12:42 | 240 / 299 |
| Long | 86-90 | 13:26 | 241 / 298 |
| Short Y / Z / AA | 91-94 / 95-97 / 98-100 | 56.6s / 46.2s / 54.4s | 242-244 / 296, 295, 297 |
| Long | 91-94 | 13:32 | 245 / 302 |
| Long | 95-97 | 9:47 | 246 / 300 |
| Long | 98-100 | 10:36 | 247 / 301 |

Commit: "feat: manhua-series -- Dai Quan Gia ch81-100 + ep95-100 scripts".

- Mọi Long đều chia sẵn 3-5 chương (1 khối 199 beat từng fail giọng ở 51-60); lần này không phải retry giọng lần nào.
- Short chọn beat **tự động** (đều nhau trong mỗi chương) nên mạch kể rời rạc hơn các Short chọn tay trước đó.
- Ch 81-88 dùng số trang gốc (ánh xạ sang khung qua `panel_pages.json`), ch 89-100 dùng khung của `cut`.
- Lỗi `recap.py`: danh sách asset bị chặn ở 3000 mục nên build Long báo "asset đã đăng ký"; đã sửa để tra theo tên file khi không thấy (commit 54d73ec).
- `STORY.md` thêm 5 Long (ch 81-100).
