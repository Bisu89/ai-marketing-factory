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

## Kết quả (2026-10-08, chương 1-10, đã render, Final QA PASS 100)
| Video | Thư mục script | Project / job | Độ dài | Khổ |
|---|---|---|---|---|
| Short A (ch 1-3) | `short_a/` | 196 / job_253 | 57s | 1080x1920 |
| Short B (ch 4-7) | `short_b/` | 193 / job_257 | 49s | 1080x1920 |
| Short C (ch 8-10) | `short_c/` | 194 / job_258 | 55s | 1080x1920 |
| Long (ch 1-10), bản đầy đủ 147 đoạn | `long_1_10/` | 199 / job_261 | 10:21 | 1920x1080 |
| (bản rút gọn 71 đoạn, không dùng nữa) | | 195 / job_259 | 5:01 | 1920x1080 |

Mỗi `script.json` có sẵn title, description, hashtag, thumbnail (text + prompt). Title của Long giữ như Long01 cũ.
Mục lục thời gian của Long (dán vào mô tả/bình luận ghim):
```
0:00 Mở đầu: Ma Hoàng bị phản bội
0:34 Tâm ma: bị trói vào Lạc gia
0:56 Rừng Sương Mù: cái bẫy chết người
1:59 Kế lừa: Trác Phàm bán chủ?
3:07 Đột phá lên Tụ Khí cảnh
4:06 Viên ngọc giả
5:08 Luyện Huyết Anh, Thái phủ trở mặt
6:17 Một chưởng của gia chủ
7:41 Ngự Hạ Thất Thế Gia
9:15 Bức tranh trị giá ngàn vạn
```
Video nằm ở `backend/data/library/_video_composer/job_<số>_<tên>/output/`.

## Cần biết
- **Khung chương 3-10 chưa được kiểm chứng với ảnh thật** (lúc viết, công cụ đọc ảnh trả "media removed"). Chương 1-2 đã xem
  thật. Vì vậy ở Short B, Short C và các phần chương 3-10 của Long, hình có thể không khớp lời kể. Bạn xem video, chỗ nào lệch thì
  báo chương/giây để sửa số khung rồi build lại (chỉ cần sửa `script.json`, không phải cắt lại).
- `ep03`...`ep10/script.json` (bản mỗi chương một Short) là bản nháp, có `"status": "DRAFT"`, không dùng.
- Lỗi gặp khi render: FINAL_QA sập vì ffmpeg in UTF-8 mà Windows đọc cp1252 (đã sửa, xem docs/features/161). Voice edge-tts có thể
  chập chờn, nếu fail thì chạy lại run.
- Mỗi lần build mới sẽ tạo project mới, nên project cũ (Long01 = 121) vẫn còn.

## Quy trình cho 10 chương tiếp theo
1. `fetch` + `cut` + `sheets` các chương (đã có cho 21-100 ở bước fetch, chưa cut).
2. Xem sheets, ghi khung chính từng chương.
3. Viết `short_*/script.json` (3 bản) và `long_*/script.json` (1 bản) với khung dạng `thư-mục/pNNN.jpg`.
4. `recap.py build manhua-recap/<thư mục đầu> --script <file> --name "..."`, render, in mục lục bằng `recap.py timestamps`.
