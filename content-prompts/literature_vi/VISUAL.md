# VISUAL — phong cách collage giấy cắt dán (theme `collage`, ảnh bên trong kiểu poster)

Cảm hứng chung từ kiểu giải thích "giấy cắt dán" của Vox; **không** sao chép thương hiệu hay bố cục cụ thể của ai. Áp dụng cho mọi tác phẩm.

## 1. Ngôn ngữ hình ảnh
Mỗi cảnh là **một tờ poster collage**: nền một màu phẳng đổi theo cảnh, nhân vật cắt viền trắng (die-cut) có bóng nhẹ, mảnh báo cũ (chữ không đọc được),
băng keo, chấm halftone, vài hình khối giấy (tam giác, tròn, zigzag), mép giấy rách, nhiều lớp tiền–trung–hậu cảnh, **một chủ thể chính**.
Nhân vật vẽ kiểu khắc gỗ/in cổ, ít màu phẳng. Chừa ~22% phía dưới khá yên để đặt phụ đề.
Tránh: ảnh AI trình chiếu kiểu chung chung, chân thực quá mức/3D, gradient, hào quang, chuyển cảnh rườm, lặp lại cùng một bố cục, chuyển động không phục vụ kể chuyện.
Dựng bằng theme `collage` (giống bản đầu của Constantinople): nền kraft có chấm, ảnh dán trên giấy rách có băng keo, dải chữ cắt dán từng chữ đổi màu nền, số lớn, mốc thời gian, hộp bằng chứng, phụ đề nền xám. Ảnh poster (tạo từ CSV) nằm trong khung giấy; **tắt chế độ ảnh đen trắng** (chỉ bật cho ảnh tư liệu cổ).

## 2. Chữ trên hình (khác với tập tiếng Anh)
Tạo ảnh AI **hay làm hỏng dấu tiếng Việt**. Quy tắc: ảnh của kênh này **không chứa chữ**; tiêu đề lớn (1–4 từ) do Remotion vẽ (`on_screen_text` role `headline`).
Cần kiểm thử trước tập đầu: font chữ cắt dán/tiêu đề của theme (`Impact`) có thể thiếu dấu xếp chồng tiếng Việt; nếu lỗi, đổi sang font có đủ glyph (Arial/Arial Black) — đây là việc **chưa làm**, ghi trong báo cáo khi bắt đầu tập đầu tiên.

## 3. Bảng màu và chỉ dẫn
- Màu thương hiệu kênh (gợi ý, chọn khi thiết lập kênh): kem giấy `#F6EFE0`, mực `#16130F`, cam đỏ `#E8532B`, vàng mù tạt `#F2B632`, xanh dương `#2F7FB5`, đỏ đậm `#C8302F`, xanh ngọc `#2E8B6A`.
- Mỗi cảnh một màu nền; hai cảnh liền kề không trùng màu. Mỗi tác phẩm có thêm **bảng phụ riêng** (2–3 màu hợp bối cảnh) nhưng giữ cấu trúc poster.
- Màu nhấn: một màu cho "điều nguy hiểm/mất mát", một màu cho "hy vọng/ký ức" xuyên suốt tập để người xem đọc được cảm xúc theo màu.
- Ánh sáng: phẳng, bóng đổ đơn giản của giấy; không chiaroscuro.
- Tương quan chữ–hình: tiêu đề trên giấy rách ở nửa trên; phụ đề dưới; không đặt chi tiết quan trọng ở 22% dưới.

## 4. Nhất quán nhân vật (làm **trước** khi tạo ảnh của tập)
Bảng tham chiếu cho mỗi nhân vật (file `characters.md` của tác phẩm, và dòng cast dán vào mọi prompt):
tên; tuổi nếu tác phẩm nêu; khuôn mặt, dáng; tóc; trang phục; đạo cụ quan trọng; biên độ cảm xúc; ràng buộc "giữ nguyên khi xuất hiện lại".
**Không bịa chi tiết ngoại hình mà tác phẩm không nêu**; phần tự diễn giải phải ghi "diễn giải hình ảnh". Nhân vật hư cấu được phép vẽ mặt; người có thật thì dùng tư liệu hoặc cảnh xa/quay lưng.

## 5. Mẫu bố cục theo loại cảnh
| Loại | Gợi ý |
|---|---|
| Thiết lập bối cảnh | cảnh rộng, nền màu phẳng + đường chân trời giấy rách, nhân vật rất nhỏ |
| Chân dung | một nhân vật cắt viền lớn, hai mảnh giấy phụ, tiêu đề 1–3 từ |
| Tương tác | hai nhân vật đối diện, khoảng trống ở giữa mang ý nghĩa (giấy rách chia đôi) |
| Hồi tưởng | tông màu nhạt/halftone dày, viền ảnh cũ |
| Biểu tượng | một vật lớn ở giữa (đồ vật gắn với nhân vật) trên nền phẳng |
| Bản đồ/dòng thời gian | mảnh giấy bản đồ/lịch cắt dán (chỉ khi câu chuyện cần) |
| Phân tích | thẻ bằng chứng (preset EvidenceBoard) có trích dẫn + nguồn |
| Bước ngoặt | màu nền đổi mạnh, bố cục đảo so với cảnh trước |
| Kết, lắng lại | ít hình khối, nhiều khoảng trống, một chủ thể |
Mẫu chỉ để thống nhất, không bắt mọi tập theo cùng thứ tự.

## 6. Tái sử dụng tài sản
Kho `pool.csv` của kênh: tên file `<tacpham>_<tap>_<ma-canh>_<mo-ta>.png`, khung, nhân vật trong ảnh, quy tắc dùng lại (`any`/`with:<nhân vật>`), tập đã dùng, nguồn/giấy phép/prompt.
Dùng lại nền, vật thể, kết cấu giấy; **ảnh có nhân vật chính của tập luôn tạo mới**. Một ảnh một lần trong một video; hạn chế lặp tập liền trước.
Đặt phiên bản `v2`… khi sửa; ghi prompt cùng ảnh để tạo lại.

## 7. Khuôn prompt ảnh (điền được bằng code)
```
WORK: {tac_pham} — SCENE: {ma_canh}: {mo_ta_canh}
CHARACTER: {cast_line_cho_tung_nhan_vat}
ACTION: {hanh_dong}      EMOTION: {cam_xuc}
COMPOSITION: {bo_cuc_theo_loai_canh}      FRAMING: wide 16:9, 1536x1024, subject in central band, bottom 22% calm
STYLE: Modern editorial paper-collage poster, die-cut cut-out figures with white outline and soft shadow, torn paper edges, masking tape,
  newsprint scraps with illegible text, halftone dots, flat bold {mau_nen} background, simple flat paper shapes, woodcut/engraving line figures
PALETTE: {bang_mau_phu_cua_tac_pham} + channel accents
CONTINUITY: keep each character's face, hair and clothing identical to the reference line above
NEGATIVE: no text, no letters, no numbers, no watermark, no logo, no photorealism, no 3D render, no gradients, no halo, no gore
```
Ảnh do chủ kênh tạo từ CSV; không nối API sinh ảnh.
