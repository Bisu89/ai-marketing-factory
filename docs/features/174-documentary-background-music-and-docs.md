# 174 — Documentary: nhạc nền tùy chọn + bộ tài liệu

**Nhạc nền** (`render.mux_command`, tham số `music_path/music_db/music_credit`): bạn cung cấp file nhạc miễn phí bản quyền
(mp3/wav/m4a/ogg/flac, đường dẫn đầy đủ, ≤100 MB, phải có luồng âm thanh; mức -40…-6 dB). Nhạc **lặp** cho đủ độ dài, được hạ bằng
`sidechaincompress` khoá theo giọng đọc (giọng luôn nổi trên nhạc), vào dần 2 s và nhỏ dần 3 s cuối, rồi loudnorm toàn mix, 48 kHz stereo.
Mặc định tắt. Hash đầu vào gồm SHA-256 file nhạc + mức dB (đổi bài/mức ⇒ video khác, không dùng cache); `PIPELINE_VERSION` = 3.
Xuất gói: `credits.json` có mục `music`, `credits.txt`/`description.txt` ghi giấy phép/ghi công nhạc; **cảnh báo `music_no_credit`**
nếu dùng nhạc mà chưa điền giấy phép. UI Render có ô nhạc (đường dẫn, mức, giấy phép).

**Bộ tài liệu** `docs/documentary/` (README, SETUP, ARCHITECTURE, PROVIDERS, COSTS, TROUBLESHOOTING) theo brief gốc, viết từ hệ thống đã
chạy thật; `content-prompts/vox_documentary_template/HANDOFF.md` vẫn là điểm vào khi mở session/máy mới.

Kiểm chứng: test ghép âm thanh thật bằng ffmpeg (nhạc ngắn hơn video vẫn lặp và còn nghe thấy khi giọng đã hết; nhỏ dần ở cuối; giọng không bị
nhạc làm to hơn >3 dB; lệnh có `sidechaincompress`/`-stream_loop`; file nhạc sai/đường dẫn tương đối/đuôi lạ/không phải âm thanh/mức dB ngoài khoảng bị
từ chối; hash đổi theo bài nhạc và mức); chạy thật trên dự án #1 với nhạc tổng hợp tự tạo (preview 20 s, 48 kHz, 0 khung đen) và đường dẫn sai bị trả 400 rõ ràng.
Lỗi thật khi làm: test dùng `media` chưa import (bắt ngay khi chạy).
Giới hạn: không có thư viện nhạc/SFX trong app; ducking dùng tham số cố định (ngưỡng 0.02, tỉ lệ 10:1) — chưa chỉnh được từ UI; chưa nghe duyệt chất lượng nhạc thật.
Commit: "feat: documentary optional background music with ducking + documentation set".
