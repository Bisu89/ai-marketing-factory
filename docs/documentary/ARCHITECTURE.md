# Kiến trúc

```
React (frontend/src/pages/documentary/*)  ──HTTP──►  FastAPI  /api/v1/documentary/*
                                                      │  (app/modules/documentary: logic; router*.py mỏng)
                                                      ├─ SQLite (documentary_* + alembic 0009–0016)
                                                      ├─ ffmpeg/ffprobe (đo, ghép tiếng, thumbnail, blackdetect)
                                                      └─ Remotion CLI (node) ── Chromium ──► khung hình MP4 (không tiếng)
```

## Ranh giới module
`app/modules/documentary` **không import module khác**. Phần cần nối nhiều module nằm ở *composition root*
`app/api/v1/endpoints/`: `documentary_llm.py` (provider kịch bản), `documentary_tts.py` (edge + ElevenLabs),
`produced_videos.py` (liệt kê render final trên trang Videos).

## Trạng thái & cổng duyệt (`state_machine.py`, thuần, không I/O)
Chuỗi: `draft → research_review → script_review → storyboard_review → asset_generation → asset_review → audio_ready →
render_preview → final_review → approved → exported` (+ `failed`/`resume`).
5 cổng, mỗi cổng gắn bước duyệt và số phiên bản artifact: `research`, `script`, `storyboard_assets` (storyboard+ảnh),
`narration_timing`, `final`. **Vào bước T chỉ khi mọi cổng đứng trước T đang `approved` đúng phiên bản hiện tại.**
Lịch sử duyệt chỉ-thêm (approved/rejected/revoked).

**Vô hiệu hóa**: sửa một artifact (`bump_artifact`) tăng phiên bản của nó, thu hồi duyệt của nó và mọi cổng sau nó, và đưa dự án
quay về bước duyệt đó. Duyệt cũ không bao giờ được dùng lại cho nội dung mới. Mỗi cổng còn có kiểm tra nội dung riêng
(vd. cổng 2: mọi đoạn nêu sự kiện phải trích khẳng định đã xác minh/tranh cãi có nguồn; cổng 5: bản final đạt QC *và* còn khớp dữ liệu).

## Dữ liệu (SQLite)
`project`, `approval`, `source`, `claim`, `claim_source`, `script` (mỗi lần lưu = một phiên bản), `scene` (mã ổn định `S001…`, không tái sử dụng),
`asset` (giấy phép/ghi công/hash nội dung), `narration_segment` (`N001…`, khóa cache), `usage` (sổ chi phí chỉ-thêm), `segment_alignment`,
`timing_override`, `scene_timing`, `subtitle`, `render_job`, `export`. File lớn nằm ngoài DB: `<library>/_documentary/project_<id>/…`.

## Luồng dữ liệu
1. **Script → Scenes** (`storyboard.py`): cắt theo câu; phân loại preset bằng luật giải thích được; ảnh dùng chung ≤3 cảnh/nhóm; cảnh giữ nguyên
   nếu lời dẫn không đổi (giữ mã, ảnh, chỉnh tay).
2. **Scenes → Segments** (`narration.py`): ~350–900 ký tự, đóng ở ranh giới cảnh/phần. Cache theo `(hash văn bản, fingerprint giọng)`.
3. **Audio → Timeline** (`alignment.py`, `timeline.py`): ghép từ của kịch bản với timestamp (SequenceMatcher bỏ dấu/hoa/thường); từ không khớp được nội suy và gắn cờ.
   Nguồn timing: `tts_provider` → `whisper_local` → `estimated` (luôn gắn cờ) → `manual`.
4. **Timeline → Manifest** (`render_plan.py`): mọi thời điểm là frame; cảnh nối liền; chữ suy từ lời dẫn, cue theo lúc từ được đọc;
   hash đầu vào = manifest + master audio + mã nguồn Remotion + chủ đề + nhạc + `PIPELINE_VERSION`.
5. **Manifest → Video** (`render.py`): Remotion (muted) → ffmpeg mux 48 kHz (loudnorm, nhạc có ducking) → ffprobe + blackdetect → thumbnail.
6. **Export** (`export.py`): chỉ sao chép + sinh file mô tả; manifest có SHA-256.

## Remotion (`remotion/src`)
`schema.ts` (zod) là hợp đồng với backend. `Documentary.tsx` xếp cảnh bằng `Sequence`, mỗi cảnh fade-in **đè lên** cảnh trước nên không thể lộ khung đen.
9 preset × 2 chủ đề (`presets.tsx`+`collage.tsx` / `cinematic.tsx`). Cùng seed ⇒ cùng hình (giấy rách, hướng trôi) nên render lặp lại giống hệt.
Layout luôn tính trong 1920×1080; preview thu nhỏ bằng `--scale`.

## Đồng thời & độ bền
Một render/lần (semaphore); job treo sau khi app khởi động lại bị đánh dấu lỗi khi đọc; hủy được; không resume giữa chừng.
Mọi lệnh con dùng danh sách tham số (không shell, không ghép chuỗi từ dữ liệu người dùng); đường dẫn gửi cho Remotion luôn tuyệt đối.
