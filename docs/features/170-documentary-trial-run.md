# 170 — Documentary: chạy thử một dự án thật ("Constantinople 1453")

Chạy toàn bộ luồng trên **app thật** (dự án #1, cổng 8000) với nội dung thật, không gọi API
trả phí: nguồn/khẳng định lấy nguyên văn từ bài Wikipedia "Fall of Constantinople" (đối chiếu
bằng chuỗi con, không gõ lại tay), 5 ảnh tư liệu từ Wikimedia Commons (4 miền công cộng +
1 CC BY-SA 4.0, giấy phép/tác giả lấy từ API của Commons), giọng edge-tts (miễn phí).

Kết quả: 12 khẳng định (1 "còn tranh cãi" — quân số Ottoman), kịch bản 7 phần ~422 từ,
15 cảnh (7 cảnh ảnh, 8 cảnh đồ họa), 7 đoạn giọng, master 118.5s, timing từ timestamp thật của
TTS (độ phủ 86–100%), 38 phụ đề; bản cuối **1920×1080 H.264 + AAC 48 kHz, 118.57s, 0 khung đen,
0 cảnh báo**; cả 5 cổng đã duyệt. Thời gian: edge-tts ~300s (dịch vụ chập chờn, có retry),
preview 50% ~75s, bản cuối ~5 phút.

Bug thật chỉ lộ ra khi chạy trên dữ liệu và DB thật (tất cả đã sửa, có test):
- DB thật thiếu cột `documentary_scene.assigned_hash` (tạo giữa Phase 3, trước khi cột được
  thêm vào migration 0011 sửa tại chỗ) → `POST /storyboard/plan` trả 500. Thêm migration 0015
  (có kiểm tra tồn tại) và `test_migrations.py` so khớp lược đồ migration với model.
- Remotion chạy ở thư mục khác nên `./data/library` (tương đối) không tìm thấy `props.json` →
  mọi đường dẫn truyền cho Remotion giờ là tuyệt đối.
- Planner: regex "năm" coi `000` trong `7.000` là năm → cảnh quân số thành TimelineBuild; "thành
  phố" bị coi là tín hiệu bản đồ → cảnh mở đầu thành MapZoom. Sửa regex/từ khóa.
- BigNumber chỉ hiện "80.000" cho "từ 50.000 đến 80.000" → hiện cả khoảng.
- EvidenceBoard một thẻ: chữ rất nhỏ → cỡ chữ tính theo diện tích thẻ.
- Âm thanh xuất 96 kHz (loudnorm nâng tần số) → ép 48 kHz stereo, thêm cảnh báo QC và
  `PIPELINE_VERSION` vào hash để cache cũ không bị dùng lại; lỗi do chính tôi (chú thích chèn
  giữa danh sách tham số ffmpeg) được test render thật bắt ngay.

Hạn chế ghi nhận: nguồn chỉ là Wikipedia (thứ cấp) — cần đối chiếu sách chuyên khảo trước khi
đăng; ảnh CC BY-SA có điều khoản chia sẻ tương tự, nên xem lại trước khi dùng thương mại; chưa
nghe duyệt bằng tai; timeline cảnh năm (330, 1204) chưa có chú thích ngữ cảnh; Python của app
(hệ thống) có ctranslate2 2.24 cũ nên Whisper trong app không dùng được (không cần khi dùng
timestamp của TTS).
Commit: "fix: issues found running a real documentary project end to end".
