# Vox Documentary — Rule sản xuất

Áp dụng cho mọi tập. Ngắn gọn có chủ ý; lý do kỹ thuật nằm trong `HANDOFF.md` và `docs/features/`.

## 1. Thông số
| | Giá trị |
|---|---|
| Thể loại | Lịch sử: bí ẩn, thảm họa, sự kiện ít người biết, điều tra có bằng chứng |
| Độ dài | 8–10 phút (≈ 1.600–2.000 từ tiếng Việt). Độ dài thật đo từ audio, **không** từ số chữ |
| Khung hình | 1920×1080, 30 fps, 16:9 |
| Ngôn ngữ | Lời đọc tiếng Việt; giao diện/tài liệu tiếng Việt, code/API tiếng Anh |
| Giọng | edge `vi-VN-NamMinhNeural` (miễn phí, có timestamp từng từ) hoặc ElevenLabs (trả phí, cần `voice_id`) |
| Chủ đề hình ảnh | **`collage`** (chuẩn, mặc định, duy nhất trong tab Render); xem mục 8 |
| Nhạc/SFX | Mặc định tắt (chưa có tính năng) |
| Cảnh | ~35–50 cảnh/10 phút; cắt theo câu/đoạn, **không** cắt theo số giây cố định |

## 2. Nghiên cứu & khẳng định (cổng 1)
1. Mọi sự kiện/số liệu/trích dẫn phải là một **khẳng định** gắn **≥1 nguồn** thật. `verified` và `disputed` bắt buộc có nguồn.
2. **Không bao giờ bịa** URL, tác giả, ngày xuất bản, trích dẫn, thống kê. Trích đoạn nguồn phải **cắt nguyên văn** (công cụ
   `episode_builder.py` kiểm tra bằng chuỗi con; không khớp thì dừng).
3. Con số khác nhau giữa các nguồn ⇒ khẳng định `disputed` + ghi chú các cách giải thích; kịch bản phải nói rõ là tranh cãi.
4. Nguồn thứ cấp (Wikipedia) chỉ đủ cho bản chạy thử. Tập thật: đối chiếu thêm sách chuyên khảo/nguồn gốc và ghi vào mục Nguồn.
5. LLM **không** được đặt trạng thái `verified`.

## 3. Kịch bản (cổng 2)
0. Máy dựng **bắt buộc đủ 7 phần** (hook, context, timeline, evidence, turning_point, consequences, conclusion); thiếu phần nào kiểm tra kịch bản báo `missing_section`.
1. 7 phần theo thứ tự: **hook → bối cảnh → dòng thời gian → bằng chứng & cách giải thích khác nhau → bước ngoặt → hệ quả → kết luận & câu hỏi bỏ ngỏ**.
2. Hook ≤ 3 giây, một câu mạnh, không giật gân vượt quá nguồn.
3. Mỗi đoạn nêu sự kiện (`factual=true`) phải trích khẳng định; chỉ câu nối/dẫn dắt mới `factual=false`.
4. Con số trong lời dẫn viết bằng **chữ số** khi muốn hiện số lớn lên hình (7.000, 50.000 đến 80.000 binh sĩ); năm viết **4 chữ số**.
   Viết "năm 330" (có chữ "năm") cho năm 3 chữ số.
5. Câu ngắn, tự nhiên, tránh giọng AI lặp; phân biệt rõ **sự kiện chắc chắn** và **cách diễn giải còn tranh cãi**.
6. Tên riêng nước ngoài giữ nguyên chữ Latinh (Mehmed, Orban, Golden Horn); thứ tự "Mehmed Đệ Nhị", "Constantine Đệ Thập Nhất".

## 4. Ảnh (cổng 3) — kết hợp, không toàn bộ AI
1. **Ưu tiên ảnh tư liệu miền công cộng có ghi nguồn** (tranh/bản khắc cổ, chân dung thật như Bellini). Công cụ: `tools/commons.py`.
2. **Ảnh AI chỉ cho cảnh chưa có tư liệu** (vật thể, khung cảnh, hoạt động). Phong cách: `IMAGE_STYLE.md`. Người dùng tự tạo từ CSV.
3. **Không để AI vẽ mặt người có thật** (không ai biết mặt họ) — dùng chân dung tư liệu hoặc cảnh nhìn từ xa/quay lưng/trong bóng.
4. Mỗi ảnh có **giấy phép + ghi công + URL nguồn** trong app. Ảnh `archival` không có giấy phép/ghi công thì **không duyệt được**.
5. **Người dùng tự đọc giấy phép trên trang nguồn rồi mới duyệt.** Công cụ chỉ báo lại nhãn của Commons (nhãn do người đóng góp gán).
6. CC BY-SA / GFDL / FAL: có điều khoản chia sẻ tương tự — **tránh** cho kênh kiếm tiền, hoặc thay bằng ảnh miền công cộng/AI.
7. Ghi công **hiện trên màn hình** (caption) cho ảnh cần ghi công; ảnh AI gắn nhãn "Minh họa AI".
8. Một ảnh được dùng chung tối đa 3 cảnh liền kề trong một đoạn; ảnh đã duyệt có cùng prompt được tái dùng, không tạo lại.
9. Chữ, ngày, con số, nhãn **không** được vẽ trong ảnh AI — luôn là chữ do code vẽ (prompt phải ghi "no text").

## 5. Giọng đọc & timeline (cổng 4)
1. Tạo audio chỉ sau cổng 3. Backend trả phí: xem ước tính và **xác nhận** trước khi chạy; chi phí chưa biết hiển thị "chưa biết", không ghi $0.
2. Mỗi đoạn tối đa 3 lần thử cho mỗi phiên bản văn bản+giọng; sửa văn bản/đổi giọng thì được thử lại.
3. **Nghe lại toàn bộ master** trước khi duyệt. Cảnh timing "ước lượng"/khớp từ thấp phải nghe và chỉnh tay hoặc căn chỉnh lại.
4. Đổi giọng/thông số ⇒ mọi đoạn bị đánh dấu cũ (cần tạo lại).

## 6. Render & duyệt cuối (cổng 5)
1. Preview rẻ trước (15–60 giây đầu, 25–50%), rồi mới render bản cuối 1920×1080.
2. Bản cuối phải đạt kiểm tra tự động: độ phân giải, 30 fps, có tiếng 48 kHz, thời lượng, không cắt lời, **không khung hình đen**.
   Đạt kiểm tra tự động **không** thay cho nghe/xem của người.
3. Đổi bất kỳ dữ liệu nào sau khi render ⇒ bản render đó `stale`, phải render lại.

## 7. Đăng (ngoài phạm vi công cụ)
- Công cụ **không tự đăng**. Khi đăng lên YouTube: khai báo nội dung tổng hợp/AI nếu có ảnh AI trông như thật về sự kiện/người thật
  (kiểm tra chính sách hiện hành), ghi nguồn + ghi công ảnh trong mô tả, tiêu đề không giật gân quá nguồn.
- Rủi ro kênh: loạt video làm hàng loạt từ hình AI có thể bị coi là nội dung sản xuất đại trà — giữ ảnh tư liệu thật, nguồn rõ, lời dẫn độc đáo.

## 8. Phong cách chuẩn: `collage` (chốt 2026-10-09, áp dụng cho mọi truyện kể)
Nhìn như bản đầu của Constantinople: nền **kraft có chấm**, ảnh **dán trên giấy rách có băng keo** (nhãn ghi công/"AI illustration" ở góc), dải chữ **cắt dán
từng chữ đổi màu nền** cho tiêu đề, **số lớn**, mốc thời gian, hộp bằng chứng có dấu "CÒN TRANH CÃI" khi khẳng định bị tranh cãi, phụ đề **nền xám** viền vàng.
Quy ước:
1. **Nhịp:** ảnh xen thẻ dữ liệu (khoảng 40–50% cảnh là thẻ như Constantinople); một chuỗi toàn ảnh trôi chậm là chưa đúng phong cách.
2. **Thẻ dữ liệu** (`HeadlineImpact`, `EvidenceBoard`, `BigNumber`, `TimelineBuild`, `MapZoom`, `SplitComparison`): chữ cắt từ chính lời đọc. Tiếng Việt: bộ luật tự dò chữ chạy được; **tiếng Anh/ngôn ngữ khác: viết tay `scene_overrides`** (`texts: [[chữ, vai trò]]`).
3. **Thẻ không có ảnh** hiện chữ ngay từ đầu cảnh (trừ mốc năm/số lớn, hiện theo lời đọc) để khỏi có khung trống.
4. **Màu ảnh:** ảnh màu (AI, tranh màu) → **tắt "Ảnh đen trắng"** ở tab Render (mặc định tắt). Chỉ bật cho ảnh tư liệu cổ muốn đồng nhất tông xám.
5. **Ảnh bên trong khung giấy:** ảnh tranh/ảnh AI 16:9 (Baroque của Biblical Figures hoặc ảnh kiểu poster collage — xem `IMAGE_STYLE.md`); ảnh dọc được xử lý nền mờ.
6. Không nhúng chữ vào ảnh AI (chữ do code vẽ; riêng tiếng Việt vì AI hay hỏng dấu).
7. Preview thử chỉ 30–70 giây (`seconds`), không render đủ tập.
8. `cinematic` và `poster` đã bỏ khỏi UI; engine còn code nhưng **không dùng** nếu chủ kênh chưa nói. Không tự đổi phong cách.
