# 182. Đại Quản Gia ch 81-91: review và viết lại script từng tập

Đối chiếu từng trang ảnh (ch 81-88) hoặc từng khung đã cắt (ch 89-91) với `ep81..ep91/script.json` rồi viết lại. Lỗi tìm thấy ở hầu hết các tập: gán sai trang cho câu thoại, bỏ sót cảnh quan trọng, đổi sai người nói, lược mất chi tiết móc câu; tiêu đề thiếu "!?"; không có bình luận thật (chỉ có beat gắn nhãn commentary mà vẫn là kể lại). Ví dụ nặng: ep89 viết sai cấu trúc công pháp (thực tế 3 tầng Luyện Cơ / Luyện Cốt / Luyện Ngũ Tạng rồi nguyên thần), và dùng khung p081 chỉ là watermark; ep90 đảo người hỏi/người trả lời trong cảnh Hòa Thần; ep91 viết Ngưng Nhi "chất vấn" trong khi cô kề dao vào cổ mặc cả; ep88 đoạn "thái độ không quan tâm" thực ra là nội tâm Thiên Dương.

Kết quả: mỗi tập 24-43 beat, 1-3 bình luận (kind `commentary`), tiêu đề kết "!?" dưới 70 ký tự, beat cuối luôn là kể lại (cliffhanger), `type` chỉ dùng HOOK/BUILD/ENDING.

Commit: "fix: manhua-series -- review and rewrite Dai Quan Gia ep81-91 scripts".

Cần biết khi build:
- Ch 81-88: số `pNNN` là **số trang ảnh gốc** (trang là dải dài), không phải khung của `cut`. Khi build phải ánh xạ trang -> khung đầu tiên của trang đó qua `_recap/panel_pages.json` (như ch 71-80).
- Ch 89-91: số `pNNN` là **khung của `cut`** (đã cắt lại cả 11 chương, `_recap/panels` mới).
- Tên công pháp thống nhất "Thiên Ma Đại Hóa Quyết" (ep88 trong ảnh dịch là "Thiên Quỷ").
- Chưa build/render ch 81-91.

## Bổ sung: ep92-94 (2026-10-13)
Review tương tự: ep92 (khung cut, 69 khung) và ep93/94 (97/82 khung) đều viết lại. Lỗi nặng nhất ở **ep93**: script cũ cho Trác Phàm xuất hiện và mở "hiệp hai" ngay trong tập này, nhưng thực tế ep93 là Ngưng Nhi lên kiệu hoa, chiếc nhẫn Lôi Linh sáng, **Thiên Dương** lao vào cứu rồi bị U Quỷ Thất đánh gục, kết bằng Bát trưởng lão xuất hiện; Trác Phàm chỉ xuất hiện ở cuối **ep94**. Ep94 cũng bỏ qua cảnh U Quỷ Thất lôi cả Tiết gia bị trói ra và cảnh Bát trưởng lão bỏ đi. Ep92: tên tập có "luyện hóa Thanh Viêm", lão nhân tặng Thanh Viêm là mạch phụ nên được giữ lại như một đoạn riêng.
Số `pNNN` của ep92-94 là khung của `cut` như ep89-91.
