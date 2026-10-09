# 167 — Documentary: alignment, timeline & subtitles (Phase 4b)

Timing đến từ **audio thật**, không phải ước lượng độ dài chữ. ffprobe chỉ đo
thời lượng file; thời điểm từng từ đến từ timestamp của TTS hoặc Whisper.

- **Căn chỉnh** (`alignment.py`): ta đã biết chính xác lời dẫn, nên đây là
  *căn chỉnh*, không phải nhận dạng — khớp từ của kịch bản với (từ, bắt đầu,
  kết thúc) nhận được bằng so khớp chuỗi (bỏ qua hoa/thường, dấu câu, dấu
  tiếng Việt). Từ không khớp được nội suy giữa hai từ neo thật và bị gắn cờ
  `matched=false`, nên khớp yếu hiện ra chứ không bị tin ngầm.
- **Nguồn timestamp**, theo thứ tự: `tts_provider` (edge-tts / ElevenLabs trả
  sẵn, nếu độ phủ ≥ 85%) → `whisper_local` (faster-whisper, CPU int8, model
  `small`, cấu hình `APP_DOCUMENTARY_WHISPER_MODEL`) → `estimated` (đoán theo độ
  dài từ, luôn bị gắn cờ cần duyệt). Chọn tay bằng `method`.
- **Cache theo đoạn**: kết quả căn chỉnh gắn với `cache_key` của audio đoạn đó
  (Whisper chạy chậm nhất nên chỉ chạy lại cho đoạn đổi). Dựng timeline là
  phép tính thuần từ căn chỉnh đã lưu + offset master hiện tại.
- **Timeline** (`timeline.py`): mỗi cảnh có start/end tuyệt đối trên master,
  liền mạch (cảnh chạy tới khi cảnh sau bắt đầu, nên không hở/chồng), cảnh đầu
  bắt đầu 0s, cảnh cuối kết thúc đúng cuối audio. `actual_duration` của cảnh được
  điền từ đây. Nguồn và độ phủ hiển thị theo từng cảnh.
- **Phụ đề**: tách theo câu (câu >84 ký tự tách tại dấu phẩy), lưu DB, xuất
  SRT; kiểm tra thứ tự, thời lượng dương, nằm trong audio, phủ ≥98% số từ.
- **Chỉnh tay**: `PUT .../timeline/scenes/{scene}/start` dời ranh giới cảnh
  (giữ ≥0.2s cho cảnh kề); lưu theo đoạn audio nên tự mất hiệu lực khi audio
  đoạn đó tạo lại. Cảnh đầu của đoạn do audio quyết định, không chỉnh được.
- **Cổng 4**: cần audio hiện hành, master mới, đã dựng timeline và không có lỗi
  cấu trúc (hở/chồng, ngoài audio, thời lượng ≤0, phụ đề sai, timing cũ). Cảnh
  `estimated`/khớp <70% là **cảnh báo** liệt kê theo scene ID — người duyệt có
  thể chấp nhận, nhưng không bao giờ bị giấu.
- Migration `0013_documentary_timeline` (up/down/up).

Kiểm chứng thật (không chỉ mock):
- Whisper `small` trên CPU i5-12400: **7.0s cho 10.8s audio**; so với timestamp
  gốc của edge-tts, lệch trung bình **0.042s** (tối đa 0.12s) trên 31 từ khớp.
  Độ phủ 79.5% vì Whisper viết "1453" còn kịch bản viết "một nghìn bốn trăm…"
  — phần số được nội suy giữa hai từ neo thật và gắn cờ.
- Luồng HTTP đầy đủ với edge-tts thật (7 đoạn, master 44.39s): tạo audio → gọi
  lại = 7/7 cache → ghép master → căn chỉnh (`tts_provider`, độ phủ 0.89–0.97)
  → dựng 9 cảnh liền mạch + 12 phụ đề → cổng 4 duyệt được.
- 134 test documentary pass 2 lần (Whisper được thay bằng transcriber giả).

Bug/ghi chú bắt được:
- `ctranslate2 4.8.2` sập (access violation) khi nạp *bất kỳ* model nào trên
  máy này; `4.6.0` chạy được nhưng cần `setuptools<81` (pkg_resources). Đã ghim
  trong `requirements.txt` kèm lý do.
- Endpoint duyệt cổng tự gọi `get_settings()` thay vì dùng thư mục của request
  → giờ `_svc` truyền `library_root` từ cùng `Settings`.
Giới hạn: Whisper nên dùng khi TTS không có timestamp (ElevenLabs
`/with-timestamps` chưa kiểm chứng với API thật); `faster-whisper` chưa vào
`AIContentLibrary.spec` nên bản đóng gói chưa dùng được; model `small` có thể
nhận dạng sai tên riêng — chỉ ảnh hưởng độ phủ, không ảnh hưởng timing các từ
đã khớp. Chưa có giao diện.
Commit: "feat: documentary audio-first alignment, timeline and subtitles".
