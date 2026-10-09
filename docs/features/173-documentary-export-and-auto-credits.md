# 173 — Documentary: export, ghi công tự động, chú thích timeline

**Export** (`export.py`, `router_export.py`, tab "Xuất", bảng `documentary_export`, migration 0016): sau cổng 5 tạo một thư mục
`<library>/_documentary/project_<id>/export/<slug>_<thời điểm>/` gồm `video.mp4` (sao chép bản final đã kiểm tra, không mã hóa lại),
`subtitles.srt`, `credits.json/.txt` (mọi ảnh: nguồn gốc, giấy phép, tác giả, URL, cảnh dùng, prompt nếu là ảnh AI),
`sources.json` (nguồn + khẳng định + trạng thái + nguồn nào hỗ trợ khẳng định nào), `script.md` (kịch bản có tham chiếu `[cN]`),
`timeline.json`, `description.txt` (mô tả đăng nháp: chương theo mốc thời gian thật, nguồn gộp theo URL, ghi công ảnh, lưu ý tranh cãi)
và `manifest.json` (phiên bản từng artifact, render/QC, SHA-256 mọi file). Điều kiện: dự án `approved`/`exported` **và** bản final
còn khớp dữ liệu hiện tại (đổi gì sau render ⇒ từ chối). Xuất lần đầu chuyển dự án sang `exported`; xuất lại tạo thư mục mới.
Cảnh báo (không chặn): giấy phép CC BY-SA/GFDL/FAL/không rõ, ảnh chưa duyệt, có ảnh AI (cân nhắc khai báo), cảnh timing chưa xác nhận,
cảnh báo QC. Không đăng đi đâu; không ghi ngoài thư mục xuất.

**Ghi công/nhãn tự động trên hình** (`render_plan.credit_text`): cảnh PhotoKenBurns/ArchivalPortrait dùng ảnh AI tự có nhãn
"Minh họa AI"; ảnh tư liệu giấy phép cần ghi công (không phải miền công cộng/CC0) tự có "Ảnh: <tác giả> · <giấy phép>"; ảnh miền công
cộng/ảnh tự nhập không thêm gì. Không bao giờ thêm nếu cảnh đã có chữ caption/label do người nhập. Đổi giấy phép ⇒ đổi hình ⇒ bản render cũ lỗi thời.

**Chú thích ngữ cảnh cho cảnh timeline** (`date_context`): mỗi năm hiện kèm cụm lời dẫn quanh nó (cắt từ chính lời dẫn, ≤7 từ;
VD "330 — Constantinople là kinh đô của đế quốc", "1204 — trong cuộc Thập tự chinh thứ tư"), ở cả collage và cinematic.

Sửa kèm: cổng 5 cũ bị thu hồi **trước** khi báo job "succeeded" (trước đó người xem trạng thái ngay lúc đó có thể thấy "succeeded" cạnh
duyệt cũ còn hiệu lực).
Kiểm chứng: test xuất (bundle đủ 9 file, hash khớp, CC BY-SA bị cảnh báo, chỉ sau cổng 5, từ chối khi dữ liệu đổi sau render, xuất lần hai
thư mục riêng, slug ASCII), test nhãn/ghi công tự động và `date_context`; chạy thật trên dự án #1: render lại final cinematic
(1920×1080, 48 kHz, 0 khung đen) → duyệt thử → xuất 9 file (137 MB video) với đúng 1 cảnh báo (CC BY-SA).
Giới hạn: bản duyệt cổng 5 của dự án #1 là duyệt **thử** của tôi, người dùng chưa xem/nghe; mô tả nháp chưa có tóm tắt viết tay.
Commit: "feat: documentary export bundle, automatic credit labels, timeline context captions".
