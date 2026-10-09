# Biblical Figures theo phong cách Vox (từ tập 6) — làm tiếp ở máy khác

Từ **tập 6** series dùng quy trình Vox của repo (theme **`collage`** — giấy kraft, ảnh dán giấy rách có băng keo, chữ cắt dán, số lớn, phụ đề nền xám).
Tập 1–5 giữ bản render cũ. Đọc trước: `content-prompts/vox_documentary_template/HANDOFF.md`, `biblical-figures-prompts/SERIES.md`, `RULES.md`.

## Trạng thái tập 6 (2026-10-09)
- Dự án #2 trong DB của máy gốc (`backend/data/library.db`) — **DB không nằm trong git**. Spec + công cụ trong git đủ để **tạo lại** dự án.
- `vox/ep6.spec.json`: 19 nguồn nguyên văn (Kinh Thánh bản WEB, Josephus bản Whiston, Wikipedia), 27 khẳng định, kịch bản 39 đoạn 1.198 từ (≈ 6 phút 23 giây với giọng `edge_en`), 23 cảnh thẻ dữ liệu (`scene_overrides`), danh sách ảnh.
- Cổng 1–4 đã được duyệt (cổng 3–4 do AI duyệt thay theo cho phép của chủ kênh, chưa nghe lại giọng). **Cổng 5 (duyệt cuối) chưa duyệt**; còn thay ảnh Baroque bằng ảnh kiểu poster khi có thời gian.
- Bản render: `backend/data/library/_documentary/project_2/render/job_16` (collage final; job cũ là cinematic/poster thử nghiệm).

## Tạo lại ở máy khác
1. Chạy backend (HANDOFF mục 6; chạy từ thư mục tạm khi thử nghiệm để không ghi `.env` thật).
2. **Chép ngoài git** (ảnh nặng không commit): `biblical-figures-prompts/biblical_figures_ep6_long_images/`, `_pool/` ảnh các tập 2/3/5 dùng lại, `vox/poster_test/S0xx_poster.png`. Đường dẫn ảnh trong spec là tuyệt đối của máy gốc → sửa lại `path` hoặc chạy bằng `images` sau khi chép.
3. `python content-prompts/vox_documentary_template/tools/episode_builder.py create biblical-figures-prompts/vox/ep6.spec.json` (xóa `ep6.spec.state.json` trước nếu muốn tạo mới).
4. Duyệt cổng 1–2 trong app → `storyboard` → `images` → duyệt ảnh + cổng 3 → tab Giọng đọc: backend **`edge_en`**, chia đoạn, tạo, master, căn chỉnh `tts`, dựng timeline → cổng 4 → tab Render: **collage**, tắt "Ảnh đen trắng", bản cuối.

## Tập 7 trở đi
Copy `ep6.spec.json` làm khuôn: đổi nguồn (`fetch` kiểu `bible`/`wikisource`/`wikipedia`), claims, kịch bản (kết bằng câu outro cố định: *If you made it this far, subscribe. A new figure from history every week.*), `scene_overrides`, ảnh. Ảnh tạo từ CSV (`_tools/bf.py prompts`/ hoặc prompt trong `vox/poster_test/STYLE.md`); chữ trên màn hình do code vẽ, không nhúng chữ vào ảnh.

## Bài học (đừng lặp lại)
- Không tự đổi phong cách chốt (collage). `cinematic`/`poster` đã bỏ khỏi UI.
- Preset dữ liệu (timeline/evidence/headline) cho tiếng Anh phải **viết tay** `scene_overrides`; bộ luật tự dò chữ viết cho tiếng Việt.
- Preview thử nghiệm chỉ nên 30–70 giây (`seconds`), không render đủ tập.
- Trích dẫn phải cắt từ nguồn thật (`fetch`), bỏ chi tiết không có nguồn ("months later", pháo đài Machaerus…).
