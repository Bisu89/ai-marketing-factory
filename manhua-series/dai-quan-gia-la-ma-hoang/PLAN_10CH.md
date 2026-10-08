# Kế hoạch mới: mỗi 10 chương = 3 Short + 1 Long (Claude tự viết, không dùng OpenAI)

Thay đổi so với trước (mỗi chương một Short):

| | Trước | Từ 2026-10-08 |
|---|---|---|
| Short | 1 chương = 1 Short | 10 chương = **3 Short tổng hợp** (chia theo arc) |
| Long | Long01 gộp chương 1-10 | vẫn **1 Long cho 10 chương**, có title + description + hashtag + thumbnail |
| Người viết | Claude, đôi khi thử GPT ngoài | **Claude tự đọc khung và viết**, không gọi OpenAI |
| Khung ảnh | mỗi script chỉ dùng 1 thư mục | script dùng được khung của nhiều thư mục (xem dưới) |

## Hỗ trợ nhiều thư mục trong một script
`tools/manhua_recap/recap.py build` giờ nhận `"panel": "dqgl_ep3/p004.jpg"` (thư mục chương/khung).
Khung không có tiền tố vẫn lấy từ chính thư mục đang build. Nhờ vậy 1 Short tổng hợp dùng khung đã cắt của
nhiều chương mà không phải cắt lại. Chạy: `recap.py build manhua-recap/dqgl_ep1 --script <file>` (thư mục
`dqgl_ep1` chỉ là gốc để tìm các thư mục anh em).

## Chia 10 chương (dự kiến, theo SERIES.md)
| Video | Chương | Nội dung chính |
|---|---|---|
| Short A | 1–3 | Ma Hoàng bị đệ tử phản bội, nhập thân gia nô, tâm ma buộc phải bảo vệ Lạc gia, dắt hai chị em chạy vào rừng |
| Short B | 4–7 | Bẫy Rừng Sương Mù, lên Tụ Khí cảnh, mua ngọc giả ra Huyết Tinh Linh, luyện Huyết Anh, bị Thái phủ coi thường |
| Short C | 8–10 | Đỡ một chưởng của gia chủ Thái gia, biết Ngự Hạ Thất Thế Gia, mang trận đồ tới Tiềm Long Các |
| Long | 1–10 | Tóm tắt cả 10 chương, có mục lục thời gian (đã có bản `long01/script.json`, project 121) |

Title, description, hashtag, thumbnail của từng video nằm trong `script.json` của nó (xem `ep19/script.json` làm mẫu).

## Tình trạng thật (cần biết)
- Đã xem ảnh thật: chương 2 (p001–p070) và một phần chương 1 (p001–p036, p079–p114).
- **Chưa xem được ảnh chương 3–10** (công cụ đọc ảnh trả "media removed"). Vì vậy `ep03`…`ep10/script.json`
  mình viết hôm nay là **bản nháp, số khung đoán**, đã gắn `"status": "DRAFT"`. Đừng build từ các file đó.
- 3 Short + Long mới **chưa viết**, vì cần xem lại ảnh chương 3–10 để chọn khung đúng.
- `manhua-recap/dqg_long01` đang trống trên máy này, nên bản Long01 cũ không dựng lại được nếu không tải lại ảnh.
  Hướng tiếp: dựng Long mới từ khung `dqgl_ep1..10` bằng cú pháp nhiều thư mục ở trên.

## Việc còn lại (theo thứ tự)
1. Xem lại sheets chương 1–10 (đọc được ảnh), ghi chú khung chính từng chương.
2. Viết `short_a/`, `short_b/`, `short_c/` và `long_1_10/script.json`.
3. `recap.py build` từng bản, render, in mục lục thời gian cho Long.
4. Cập nhật `SERIES.md` + bảng này khi xong.
