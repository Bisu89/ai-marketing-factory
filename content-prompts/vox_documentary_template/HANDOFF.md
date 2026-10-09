# VOX DOCUMENTARY FACTORY — HANDOFF (đọc file này đầu tiên khi mở session/máy mới)

Cập nhật: 2026-10-09. Mọi thứ dưới đây đã được **chạy thật** trên repo này (không phải kế hoạch), trừ mục
"Chưa làm". Tài liệu ngắn hơn cho từng tính năng nằm ở `docs/features/163…172-*.md`.

## 1. Đây là gì

Công cụ dựng **phim tài liệu lịch sử 8–10 phút (tiếng Việt, 16:9)** theo kiểu giải thích của Vox, chạy **cục bộ**
trong app AI Content Library (FastAPI + React + SQLite) với Remotion để vẽ hình. Mục tiêu: một chủ đề → video
hoàn chỉnh, trong đó **mọi khẳng định lịch sử đều có nguồn thật** và **con người duyệt ở 5 cổng**; không tự đăng.

Nguyên tắc cốt lõi (đừng phá):
1. **Không bịa**: nguồn/khẳng định do người nhập hoặc cắt *nguyên văn* từ nguồn thật; AI chỉ sắp xếp/diễn đạt lại.
2. **Backend ép buộc cổng duyệt**, UI chỉ hiển thị lỗi của backend. Sửa nội dung đã duyệt ⇒ thu hồi duyệt các cổng sau nó.
3. **Chi phí gần 0**: ảnh do người dùng tạo tay từ CSV hoặc lấy ảnh tư liệu có nguồn; giọng edge-tts miễn phí;
   Whisper (nếu cần) chạy máy; không AI video, không API sinh ảnh. Backend trả phí (ElevenLabs) luôn đòi `confirm=true`.
4. **Chữ trên màn hình do code vẽ** (không nhúng trong ảnh AI → không sai chính tả).
5. **Timing lấy từ audio thật** (timestamp của TTS hoặc Whisper), không dùng ước lượng độ dài chữ; ước lượng luôn bị gắn cờ.
6. **Ảnh phải có giấy phép + ghi công**; app không bao giờ tự coi ảnh trên mạng là dùng được. Người dùng tự duyệt ảnh.

## 2. Đọc theo thứ tự

1. File này.  2. `RULES.md` (quy tắc sản xuất)  3. `IMAGE_STYLE.md` (khối prompt ảnh AI kiểu Baroque + chiến lược
kết hợp ảnh tư liệu)  4. `README.md` (làm một tập mới từng bước)  5. `examples/constantinople_1453.spec.json` (tập mẫu đã chạy)
6. `docs/features/163…172` (chi tiết kỹ thuật từng tính năng)  7. Memory: `project_vox_documentary_factory.md`,
`feedback_isolate_e2e_from_env.md`.

## 3. Trạng thái hiện tại (snapshot)

| Hạng mục | Trạng thái |
|---|---|
| Phase 1–5 backend + giao diện + 5 cổng duyệt | **Xong, đã commit** (xem mục 9) |
| Chủ đề hình ảnh | `collage` (giấy cắt dán) và **`cinematic`** (ảnh tràn khung, nền tối, chữ vàng — người dùng thấy collage "lởm", cinematic là mặc định trong UI) |
| Dự án chạy thử thật | **Dự án #1 "Constantinople 1453"** trong DB thật (`backend/data/library.db`), trạng thái `approved`. Bản cuối collage 1920×1080 118.57s tại `backend/data/library/_documentary/project_1/render/job_5/output.mp4`; preview cinematic ở `job_6`. Đã render **bản cuối cinematic** (job 7) và **xuất** thử (trạng thái `exported`; cổng 5 là duyệt thử của AI, người dùng chưa xem/nghe). |
| Ảnh của dự án #1 | 4 ảnh miền công cộng + 1 ảnh **CC BY-SA 4.0 (Tường thành — cần thay trước khi dùng thương mại)**. Do tôi (AI) bấm duyệt khi chạy thử, **người dùng chưa tự duyệt** — xem `RULES.md` mục Ảnh |
| Test | `pytest tests/modules/documentary` ≈ 170+ test pass (~3 phút); `npx tsc -b --noEmit` (frontend) và `npx tsc --noEmit` (remotion) sạch |
| Export (Phase 6, xong) | Tab **Xuất**: gói 9 file (video, SRT, credits, sources, script, timeline, description, manifest+SHA-256); ghi công/nhãn "Minh họa AI" tự động trên hình; chú thích ngữ cảnh cho năm trong cảnh timeline (feature 173) |
| **Chưa làm** | nhạc nền/ducking + SFX, bộ tài liệu theo brief gốc (README/SETUP/ARCHITECTURE/PROVIDERS/COSTS/TROUBLESHOOTING), đóng gói PyInstaller (`remotion/` + faster-whisper), prompt ảnh AI tự động theo từng cảnh, tập thứ hai |

## 4. Kiến trúc (file map)

```
backend/app/modules/documentary/        # module độc lập (không import module khác; xem backend/app/modules/README.md)
  state_machine.py   11 trạng thái + 5 cổng; luật: vào bước T chỉ khi mọi cổng đứng trước T đang "approved" đúng phiên bản
  models.py          bảng documentary_* (project, approval[append-only], source, claim, claim_source, script, scene, asset,
                     scene_counter, narration_segment, usage[sổ chi phí], segment_alignment, timing_override, scene_timing,
                     subtitle, render_job)
  service.py         vòng đời dự án + duyệt cổng + bump_artifact (thu hồi duyệt) + kiểm tra nội dung từng cổng
  research.py        nguồn/khẳng định (verified/disputed bắt buộc có nguồn)
  script.py, script_providers.py   kịch bản 7 phần; provider "mock" (offline) + "llm" đăng ký từ composition root
  storyboard.py      cắt cảnh theo câu; StoryboardPolicy (phân loại preset, nhóm ảnh dùng chung, KHÔNG BAO GIỜ chọn AI video)
  assets.py          kho ảnh, kiểm tra giấy phép, vòng CSV thủ công, tái dùng theo input_hash, stale theo assigned_hash
  narration.py, tts.py, media.py   chia đoạn ~350–900 ký tự, cache theo (hash văn bản + fingerprint giọng), retry ≤3, ngân sách, master
  alignment.py, align_whisper.py, timeline.py   căn chỉnh script↔timestamp, timeline cảnh liền mạch, phụ đề, SRT, chỉnh tay
  render_plan.py     manifest cho Remotion (cue chữ theo lúc từ được đọc, suy chữ từ lời dẫn), hash đầu vào, preflight
  render.py          job nền (1 render/lần), gọi Remotion CLI + ffmpeg mux 48kHz + ffprobe + blackdetect, thumbnail
  router*.py         API /api/v1/documentary/*  (63+ route; xem /openapi.json)
backend/app/api/v1/endpoints/            # composition roots (được phép nối nhiều module)
  documentary_llm.py (provider kịch bản dùng llm_client) · documentary_tts.py (edge + ElevenLabs)
  documentary_media.py · produced_videos.py (liệt kê render final trên trang Videos)
backend/alembic/versions/0009…0015_documentary_*.py   (0015 = vá cột assigned_hash thiếu trên DB dev)
remotion/src/                            # package Node riêng (remotion 4.0.534 ghim chính xác, zod 3.22.3)
  schema.ts (manifest zod) · theme.ts + collage.tsx + presets.tsx (collage) · cinematic.tsx · Documentary.tsx · Root.tsx
frontend/src/pages/DocumentaryListPage.tsx, DocumentaryProjectPage.tsx, documentary/*Tab.tsx   (tiếng Việt)
frontend/src/api/documentary.ts
content-prompts/vox_documentary_template/    # thư mục này: quy tắc, prompt, template, công cụ dựng tập
```

Dữ liệu trên đĩa: `<library_dir>/_documentary/project_<id>/{assets,narration,render/job_<id>}`; `library_dir` mặc định
`./data/library` (tương đối so với thư mục chạy backend).

## 5. Quy trình một tập (ai làm gì)

| Bước | Ai | Cách |
|---|---|---|
| 1. Chọn chủ đề, nguồn, khẳng định | Người + công cụ | `tools/episode_builder.py create spec.json` (cắt trích đoạn nguyên văn từ Wikipedia theo "needles") hoặc nhập tay ở tab Nghiên cứu |
| 2. **Cổng 1** duyệt nghiên cứu | **Người** | tab Tổng quan |
| 3. Kịch bản (7 phần, mỗi đoạn gắn khẳng định) | Người/AI | spec hoặc tab Kịch bản (provider `mock` miễn phí, `llm` tốn token) |
| 4. **Cổng 2** duyệt kịch bản | **Người** | kiểm tra tự động: mọi đoạn nêu sự kiện phải trích khẳng định đã xác minh/tranh cãi có nguồn |
| 5. Storyboard | Công cụ | `episode_builder.py storyboard spec.json` hoặc tab Storyboard |
| 6. Ảnh | Người | ảnh tư liệu (`episode_builder.py images`) + ảnh AI tự tạo từ CSV (`IMAGE_STYLE.md`); **đọc giấy phép từng ảnh rồi duyệt** |
| 7. **Cổng 3** | **Người** | |
| 8. Giọng đọc (edge miễn phí / ElevenLabs trả phí), master, căn chỉnh timeline | Công cụ | tab "Giọng đọc & Timeline"; nghe lại master |
| 9. **Cổng 4** | **Người** | nghe toàn bài; cảnh timing "ước lượng" bị liệt kê |
| 10. Render preview → bản cuối (chọn chủ đề cinematic/collage) | Công cụ | tab Render; bản cuối phải đạt kiểm tra tự động |
| 11. **Cổng 5** + đăng | **Người** | **chưa có** export/đăng tự động — người tự lấy file ở trang Videos |

## 6. Chạy & phát triển

```
# backend (đúng venv; app thật của người dùng chạy bằng Python HỆ THỐNG với --reload ở cổng 8000)
cd backend && .venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
python -m pytest tests/modules/documentary -q          # ~3 phút; test render Remotion thật chạy nếu có node+ffmpeg
cd remotion && npm install && npx tsc --noEmit         # lần render đầu tải Chromium
cd frontend && npm run dev                              # tsc kiểm tra: npx tsc -b --noEmit  (KHÔNG dùng tsc --noEmit trần)
```

### Bẫy đã gặp (đừng lặp lại)
- **`.env` thật bị ghi**: `PUT /settings/*` ghi `backend/.env` theo cwd. Test/e2e phải khởi động backend từ **thư mục tạm**
  (`cd <scratch> && python -m uvicorn app.main:app --app-dir <backend> ...`) và đặt `APP_DATABASE_URL`, `APP_LIBRARY_DIR`.
- **Đường dẫn tương đối**: Remotion chạy ở cwd khác ⇒ mọi đường dẫn truyền cho nó phải tuyệt đối (đã sửa, có test).
- **Lệch lược đồ DB**: sửa migration chưa phát hành tại chỗ làm DB dev thiếu cột (`assigned_hash`). Luật: **luôn thêm
  migration mới có kiểm tra tồn tại**; `tests/modules/documentary/test_migrations.py` so khớp migration với model.
- **`ctranslate2 4.8.2` làm sập tiến trình** khi nạp model trên máy này ⇒ ghim `ctranslate2==4.6.0` + `setuptools<81` trong
  `backend/requirements.txt`. Python hệ thống của app có `ctranslate2 2.24` cũ ⇒ Whisper **không dùng được trong app**; dùng
  timestamp của TTS (`method="tts"`).
- **edge-tts chập chờn** (NoAudioReceived); đã có retry; 7 đoạn mất ~5 phút. Muốn nhanh/ổn định hơn: ElevenLabs (trả phí, cần `usd_per_1k_chars`).
- **Shell**: heredoc dài trong tool Bash hay hỏng ⇒ ghi file bằng công cụ Write/Edit.
- **Windows font**: dùng Times New Roman cho serif (Georgia vỡ dấu tiếng Việt xếp chồng).
- **Chromium của Playwright không giải mã H.264** ⇒ khung `<video>` đen trong test headless; kiểm tra hình ảnh trực tiếp từ file MP4 bằng ffmpeg.
- Starlette 0.38 chưa có Range ⇒ endpoint video tự xử lý Range.
- Hash render gồm `PIPELINE_VERSION` + mã nguồn Remotion + chủ đề: đổi cách ghép/giao diện ⇒ render lại (không dùng cache cũ).

## 7. Chủ đề hình ảnh
- `collage`: nền giấy, thẻ giấy rách, băng keo, highlight vàng, vòng đỏ (người dùng đánh giá "lởm").
- `cinematic`: ảnh tràn khung + trôi chậm (hướng theo seed của cảnh), vignette, hạt phim; ảnh dọc → nền mờ + ảnh giữa;
  cảnh dữ liệu (năm, số lớn, bằng chứng, tiêu đề) trên nền da tối viền vàng, chữ serif vàng/kem. Phụ đề không hộp, bóng chữ.
- 9 preset (đều có ở cả hai chủ đề): PhotoKenBurns, ArchivalPortrait, NewspaperStack, MapZoom, TimelineBuild, BigNumber,
  EvidenceBoard, HeadlineImpact, SplitComparison. Preset dữ liệu mà không suy ra được chữ ⇒ tự chuyển HeadlineImpact.
- MapZoom không có dữ liệu địa lý ⇒ chỉ nền đường đồng mức trang trí + ghim + nhãn.

## 8. Quyết định đã chốt với người dùng
- Làm **trong repo này** (Python/React), không Next.js/pnpm; **giữ Remotion**; Whisper chạy máy, model `small`.
- **Bỏ AI video**; chỉ lấy ý tưởng + thứ miễn phí từ dự án `vox-directer` (xem `docs/features/170…`): giao diện collage,
  mô-típ kể chuyện, cổng xem chi phí. Lý do: chi phí ~$25–160/9 phút, chữ vỡ trong ảnh AI, phụ thuộc Atlas Cloud, rủi ro kênh.
- **Ảnh = kết hợp**: ảnh tư liệu có ghi nguồn (miền công cộng) + ảnh AI phong cách Baroque của Biblical Figures cho cảnh
  chưa có tư liệu; **không toàn bộ AI**. Gắn nhãn "Minh họa AI" lên hình.
- Remotion: người dùng bảo không cần quan tâm giấy phép; brief gốc yêu cầu ghi chú — Remotion có điều kiện thương mại
  theo quy mô công ty, nên kiểm tra khi kinh doanh.

## 9. Lịch sử commit (nhánh main)
`eb4a686` nền tảng/state machine/ElevenLabs config · `7409e7e` nghiên cứu+kịch bản · `b025640` storyboard+ảnh+CSV ·
`5448a33` giọng đọc/TTS/cache/master · `082c1c3` căn chỉnh/timeline/phụ đề · `f02cb8f` giao diện · `8948fc8` render Remotion/QC/tab Render ·
`236d2af` sửa lỗi từ lần chạy thật · `cb2dafc` hiện trên trang Videos · `c063a2f` chủ đề cinematic + template này · (tiếp theo: export + ghi công tự động, feature 173).

## 10. Việc tiếp theo (theo thứ tự đề xuất)
1. ~~Export~~ (xong, feature 173).
2. **Nhạc nền tùy chọn** (ducking dưới giọng) + SFX nhẹ; mặc định tắt.
3. ~~Chú thích ngữ cảnh timeline~~ và 4. ~~nhãn ghi công/AI tự động~~ (xong, feature 173).
5. Tập thứ hai trên chủ đề thật của người dùng (dùng `README.md`); thay ảnh CC BY-SA.
6. Người dùng **xem/nghe và tự duyệt** dự án #1 (hoặc thay ảnh CC BY-SA).
7. Bộ tài liệu theo brief gốc (README/SETUP/ARCHITECTURE/PROVIDERS/COSTS/TROUBLESHOOTING) — tổng hợp từ file này + docs/features.
8. Đóng gói PyInstaller: thêm `remotion/` và faster-whisper vào `AIContentLibrary.spec`.
9. Gợi ý prompt ảnh AI theo cảnh bằng LLM (provider `llm`), vẫn xuất CSV cho người tạo tay.
