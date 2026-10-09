# 166 — Documentary: narration segments & TTS (Phase 4a)

Lời dẫn được chia thành các đoạn (~350–900 ký tự, kết thúc ở ranh giới cảnh
và luôn đóng khi đổi phần), mỗi đoạn có ID ổn định `N001…` và hash văn bản.
Sửa một câu chỉ tạo lại đúng đoạn chứa nó.

- **Cache theo đoạn** (`narration.py`): khoá = hash văn bản + fingerprint của
  backend (engine, giọng, model, thông số). Đổi giọng/thông số ⇒ mọi đoạn bị
  đánh dấu cũ (cổng 4 báo `segment_not_ready`), không bao giờ lọt qua im lặng.
- **Đo thời lượng thật** bằng ffprobe (không ước lượng); từ chối audio < 0.2s.
- **Backend** (`tts.py`, đăng ký ở `api/v1/endpoints/documentary_tts.py`):
  `mock` (im lặng, chỉ để dev/test), `edge` (miễn phí, có timestamp từng từ —
  đã chạy thật 1 câu tiếng Việt: 12 từ, 4.51s), `elevenlabs` (trả phí, key chỉ ở
  server, retry có giới hạn cho 429/5xx, không bao giờ in key trong lỗi).
  ElevenLabs gọi `/with-timestamps` để lấy căn chỉnh ký tự → từ; **chưa được
  kiểm chứng với API thật** (không gọi API trả phí), parse theo kiểu phòng thủ.
- **Chi phí**: sổ cái `documentary_usage` (chỉ thêm, không sửa) ghi ký tự và
  chi phí từng lần gọi, kể cả lần lỗi. Giá ElevenLabs không có mặc định —
  đặt `usd_per_1k_chars` ở `PUT /settings/elevenlabs`; chưa đặt thì chi phí là
  `null` ("chưa biết"), không bao giờ ghi $0 giả. Backend trả phí **bắt buộc**
  `confirm=true` sau khi xem ước tính; ngân sách dự án chặn khi vượt.
- **Retry**: tối đa 3 lần/đoạn cho mỗi phiên bản văn bản+giọng, tính theo
  `attempt_key` (sửa văn bản hoặc đổi giọng thì được thử lại).
- **Master**: ghép các đoạn (WAV 48 kHz mono, khoảng lặng 0.35s) thành
  `narration_master.wav`, lưu offset từng đoạn, chỉ ghép lại khi có đoạn đổi;
  có endpoint nghe lại toàn bài. Cổng 4 cần audio hiện hành + master mới.
- Tạo audio chỉ được phép sau khi cổng `storyboard_assets` đã duyệt; tạo lại
  audio sau khi đã duyệt cổng 4 sẽ thu hồi duyệt đó.
- Migration `0012_documentary_narration` (up/down/up trên DB tạm).

Kiểm chứng: 102 test documentary pass 2 lần (adapter ElevenLabs test bằng HTTP
mock). Bug tự bắt: ngân sách thử lại bị reset mỗi lần gọi (đã thêm
`attempt_key` và test).
Giới hạn: căn chỉnh timestamp/phụ đề local (faster-whisper) là 4b; chưa có UI.
Commit: "feat: documentary narration segments, TTS backends, cache and master".
