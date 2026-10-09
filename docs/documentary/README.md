# Vox Documentary Factory

Tạo phim tài liệu lịch sử 8–10 phút (tiếng Việt, 1920×1080, 30 fps) theo kiểu giải thích của Vox, **chạy cục bộ** trong app AI Content Library.
Chủ đề → nghiên cứu có nguồn → kịch bản → storyboard → ảnh → giọng đọc → timeline → render → xuất gói đăng.
**Con người duyệt ở 5 cổng; công cụ không bao giờ tự đăng.**

| Tài liệu | Nội dung |
|---|---|
| [SETUP.md](SETUP.md) | Cài đặt, chạy, kiểm thử |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Kiến trúc, dữ liệu, luồng trạng thái, cache/vô hiệu hóa |
| [PROVIDERS.md](PROVIDERS.md) | TTS, căn chỉnh, LLM, ảnh, render: nhà cung cấp và cách cấu hình |
| [COSTS.md](COSTS.md) | Chi phí, ngân sách, thứ gì miễn phí |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Lỗi đã gặp và cách xử lý |
| `content-prompts/vox_documentary_template/` | **Bắt đầu ở đây khi làm tập mới**: `HANDOFF.md`, `RULES.md`, `IMAGE_STYLE.md`, template, công cụ dựng tập |
| `docs/features/163…174` | Chi tiết kỹ thuật từng tính năng |

## Nó làm gì (đã chạy thật)
- Nguồn/khẳng định (`verified`/`disputed`/`unverified`); mọi đoạn nêu sự kiện phải trích khẳng định có nguồn — backend ép buộc.
- Kịch bản 7 phần, storyboard cắt theo câu, ~35–50 cảnh/10 phút, 9 preset hình ảnh, hai chủ đề (`collage`, `cinematic`).
- Ảnh = **kết hợp** ảnh tư liệu có ghi nguồn/giấy phép + ảnh AI do bạn tự tạo từ CSV (không API sinh ảnh).
- Giọng đọc có cache theo đoạn (chỉ tạo lại đoạn đổi), timing từ timestamp thật (TTS hoặc Whisper), phụ đề + SRT.
- Render Remotion → ffmpeg ghép tiếng (48 kHz, tùy chọn nhạc nền có ducking) → ffprobe + quét khung hình đen, báo lỗi theo mã cảnh.
- Xuất gói: video, SRT, ghi công ảnh, nguồn, kịch bản, timeline, mô tả nháp, manifest có SHA-256.

## Giới hạn (nói thẳng)
- Không tự đăng, không tìm nguồn tự động (nhập tay hoặc cắt trích đoạn từ bài Wikipedia); nguồn thứ cấp cần đối chiếu thêm.
- MapZoom không có dữ liệu địa lý (chỉ nền trang trí) trừ khi bạn nhập ảnh bản đồ.
- Không có resume giữa chừng khi render hỏng; không có SFX; chưa đóng gói PyInstaller cho `remotion/` + faster-whisper.
- Remotion có điều kiện giấy phép thương mại theo quy mô công ty — hãy tự kiểm tra khi kinh doanh.
