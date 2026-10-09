# 163 — Vox Documentary Factory: foundation (Phase 1)

Nền móng cho pipeline phim tài liệu lịch sử 8–10 phút: dự án, state machine
có cổng duyệt, cấu hình giọng ElevenLabs, và package Remotion.

- **Dự án + cổng duyệt:** `app/modules/documentary/` (state_machine.py thuần,
  service.py, router.py `/api/v1/documentary/*`). Backend ép buộc: chuyển sang
  state T chỉ được khi mọi cổng có review state *trước* T đang ở trạng thái
  approved đúng phiên bản artifact. 5 cổng: research, script,
  storyboard_assets, narration_timing, final.
- **Duyệt cũ không bao giờ tái sử dụng:** mỗi artifact có bộ đếm version; sửa
  artifact (`artifact-changed`) tăng version, thu hồi cổng đó và mọi cổng phía
  sau (ghi `revoked`), và đưa dự án quay lại bước duyệt. Lịch sử duyệt là
  append-only.
- **ElevenLabs:** `PUT /settings/elevenlabs` (key, voice_id, model_id,
  stability, similarity_boost, style, speed — gửi trường nào đổi trường đó),
  `GET /settings` trả `elevenlabs` mà không bao giờ lộ key. `voice_id` không
  có mặc định vì voice gắn với tài khoản. Chưa có adapter TTS (Phase 4).
- **Remotion:** `remotion/` (remotion 4.0.534 pin chính xác, zod 3.22.3 theo
  yêu cầu của Remotion). Mới chỉ có composition `Smoke`; preset thật ở Phase 5.
- **Demo:** `POST /documentary/projects/demo` tạo 1 dự án mẫu gắn nhãn
  `[MẪU]`, không chứa khẳng định lịch sử nào.
- Migration `0009_documentary` (up/down/up đã chạy trên DB tạm).

Kiểm chứng: 24 test mới (`tests/modules/documentary`) pass; `npm run
render:smoke` ra MP4 h264 1920×1080 30fps 60 frame (ffprobe).
Commit: "feat: documentary foundation -- project state machine + approval gates, ElevenLabs config, Remotion package".
