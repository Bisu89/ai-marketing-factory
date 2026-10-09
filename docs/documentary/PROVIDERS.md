# Nhà cung cấp (providers)

Mọi thứ cắm được đều có giao diện trừu tượng; chỉ nhà cung cấp *đã được cấu hình thật* mới dùng được — không có tích hợp giả.

| Việc | Giao diện | Có sẵn | Ghi chú |
|---|---|---|---|
| Kịch bản | `ScriptProvider` (`script_providers.py`) | `mock` (offline, chỉ trích nguyên văn khẳng định, câu nối gắn `[MẪU]`), `llm` (Anthropic/OpenAI qua `llm_client`) | `llm` chỉ được sắp xếp/diễn đạt lại khẳng định; claim id bịa ra bị chặn khi lưu; tốn token — UI hỏi xác nhận |
| Giọng đọc | `TTSBackend` (`tts.py`) | `edge` (miễn phí, **timestamp từng từ thật**), `elevenlabs` (trả phí), `mock` (im lặng, chỉ để thử luồng) | trả phí luôn đòi `confirm=true` sau khi xem ước tính; ElevenLabs gọi `/with-timestamps` (phân tích phòng thủ, **chưa kiểm chứng với API thật**) |
| Căn chỉnh | `alignment` + `align_whisper.py` | timestamp của TTS → faster-whisper (CPU int8, model `small`) → ước lượng (gắn cờ) | cần `ctranslate2==4.6.0` + `setuptools<81`; xem TROUBLESHOOTING |
| Nghiên cứu | thủ công | nhập tay; `episode_builder.py` cắt trích đoạn nguyên văn từ Wikipedia | chưa có provider tìm kiếm web (để dành); không bao giờ bịa nguồn |
| Ảnh | không có API | ảnh tư liệu (Wikimedia Commons qua `tools/commons.py`), ảnh AI **bạn tự tạo từ CSV** | app chỉ kiểm tra giấy phép/ghi công; **bạn tự đọc giấy phép rồi duyệt** |
| Render hình | Remotion CLI | chủ đề `collage`, `cinematic` | cần node + Chromium |
| Ghép tiếng/QC | ffmpeg/ffprobe | loudnorm, sidechain ducking, blackdetect | |
| Nhạc nền | file do bạn cung cấp | mp3/wav/m4a/ogg/flac ≤100 MB | app không có thư viện nhạc; ghi giấy phép/ghi công vào ô "giấy phép nhạc" |

## Cấu hình ElevenLabs
Tab **Cài đặt giọng** (hoặc `PUT /api/v1/settings/elevenlabs`): `api_key`, `voice_id` (không có mặc định — voice gắn với tài khoản), `model_id`,
`stability`, `similarity_boost`, `style`, `speed`, `usd_per_1k_chars` (giá gói của bạn; chưa đặt ⇒ chi phí "chưa biết"). Chỉ gửi trường nào đổi trường đó;
khóa không bao giờ được trả lại. Đổi giọng/thông số ⇒ mọi đoạn audio bị đánh dấu cũ.

## Thêm một nhà cung cấp mới
- TTS: subclass `TTSBackend` (`name`, `extension`, `paid`, `fingerprint()`, `estimate_cost()`, `synthesize()`), đăng ký bằng `register_backend` ở composition root.
  `fingerprint()` phải chứa mọi thứ làm đổi âm thanh (giọng, model, thông số) — nó là một phần khóa cache.
- Kịch bản: subclass `ScriptProvider`, `register_provider`. Chỉ được dùng claim được truyền vào.
