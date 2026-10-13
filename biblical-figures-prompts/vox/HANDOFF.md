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

## Tập 7 (Caiaphas) — dự án #4, đã làm lại bằng ảnh poster
- `vox/ep7.spec.json`: 25 nguồn nguyên văn, 29 khẳng định (3 `disputed`), 38 đoạn ~1.210 từ (6 phút 51 giây `edge_en`), thẻ chữ ~37% cảnh. **28 ảnh poster** do chủ kênh tạo từ `vox/ep7_poster_prompts.csv` (thư mục `vox/ep7_posters/`), bản Baroque cũ vẫn nằm trong spec làm dự phòng (poster đứng sau nên thắng).
- Bản render cuối: collage, ảnh màu (job #24). Cổng 1–4 đã duyệt (cổng 1–3 do AI duyệt thay theo cho phép của chủ kênh); **cổng 5 là của chủ kênh**.
- Đã bỏ khỏi bản cũ các ý không cắt được nguyên văn ("12 hộp xương / 6 người", mốc năm 26 và 36, câu Talmud, nhà thờ St Peter in Gallicantu, chữ Hy Lạp "topos").

## Tập 8 (Herod Antipas) — dự án #5, đã làm lại bằng ảnh poster
- `vox/ep8.spec.json`: 23 nguồn, 27 khẳng định (1 `disputed`), 37 đoạn ~1.352 từ (7 phút 29 giây), 58 cảnh (16 thẻ chữ). **34 ảnh poster** từ `vox/ep8_poster_prompts.csv` (thư mục `vox/ep8_posters/`; S045 dùng lại S043, S056 dùng lại S001). Render collage ảnh màu (job #25 hoặc mới hơn). Bản trước từng được chủ kênh duyệt cổng 5 và xuất gói; đổi ảnh đã thu hồi duyệt ⇒ cổng 5 cần duyệt lại.
- Đã bỏ các ý không có nguồn: mốc năm 20/34/36, "43 năm" (thành "khoảng bốn thập kỷ"), "ornament of all Galilee" (Josephus: "security of all Galilee"), đày sang Tây Ban Nha, lý do Pilate xâm phạm lãnh thổ (nay ghi là phỏng đoán).

## Ảnh dùng lại (đã biến mất khỏi thư mục làm việc → cứu vào `vox/pool_recovered/`)
10 ảnh dùng lại từ tập 2/3/4/5 (spec tập 6/7 trỏ tới đó). Ảnh `ep3_034`, `ep3_036`, `ep2_007` không cứu được.

## Tập 9 trở đi (Thomas "Doubting Thomas" — chưa có ảnh nào)
Copy `ep7.spec.json` hoặc `ep8.spec.json` làm khuôn (chúng dùng `scene_overrides` theo mã cảnh sau khi lập storyboard; hoặc dùng `cards_by_phrase` như Chí Phèo để khỏi phụ thuộc mã cảnh): đổi nguồn (`fetch` kiểu `bible`/`wikisource`/`wikipedia`), claims, kịch bản (kết bằng câu outro cố định: *If you made it this far, subscribe. A new figure from history every week.*), `scene_overrides`, ảnh. Ảnh tạo từ CSV (`_tools/bf.py prompts`/ hoặc prompt trong `vox/poster_test/STYLE.md`); chữ trên màn hình do code vẽ, không nhúng chữ vào ảnh.

## Bài học (đừng lặp lại)
- Không tự đổi phong cách chốt (collage). `cinematic`/`poster` đã bỏ khỏi UI.
- Preset dữ liệu (timeline/evidence/headline) cho tiếng Anh phải **viết tay** `scene_overrides`; bộ luật tự dò chữ viết cho tiếng Việt.
- Preview thử nghiệm chỉ nên 30–70 giây (`seconds`), không render đủ tập.
- Trích dẫn phải cắt từ nguồn thật (`fetch`), bỏ chi tiết không có nguồn ("months later", pháo đài Machaerus…).
