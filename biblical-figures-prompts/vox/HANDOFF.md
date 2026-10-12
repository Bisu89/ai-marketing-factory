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

## Tập 7 (Caiaphas) — spec đã viết, chưa tạo trong app
- `vox/ep7.spec.json`: 25 nguồn nguyên văn (Kinh Thánh bản WEB, Josephus Whiston quyển XVII/XVIII/XX, Wikipedia), 29 khẳng định (3 `disputed`: hộp xương 1990, các bản kể khác nhau ở đêm xét xử…), 38 đoạn, ~1.210 từ (≈ 6 phút giọng `edge_en`), 36 ảnh Baroque **có sẵn** (30 của tập 7 cũ + 6 ảnh dùng lại từ tập 2/3/4) — không cần tạo ảnh mới.
- Đã chạy `create` trên backend tạm: kịch bản qua kiểm tra nguồn. **Chưa** tạo trong DB thật; chưa có `scene_overrides` (mã cảnh chỉ có sau storyboard — như tập 6: tạo dự án → duyệt cổng 1–2 → `storyboard` → thêm thẻ chữ HeadlineImpact/EvidenceBoard/MapZoom khoảng 40–50% cảnh → `images` → cổng 3…).
- Đã bỏ khỏi bản cũ các ý **không cắt được nguyên văn**: "12 hộp xương / 6 người", mốc năm 26 và 36, câu Talmud Pesahim, nhà thờ St Peter in Gallicantu, chữ Hy Lạp "topos". Thêm mới có nguồn: hộp xương Miriam (2011), Josephus về thập phân, Gamaliel (Acts 5).
- Ảnh trong spec dùng đường dẫn tuyệt đối của máy này (`biblical_figures_ep7_long_images/`, kho tập 2/3/4).

## Tập 8 (Herod Antipas) — spec đã viết, chưa tạo trong app
- `vox/ep8.spec.json`: 23 nguồn nguyên văn (Kinh Thánh WEB, Josephus Whiston quyển XVIII, Wikipedia), 27 khẳng định (1 `disputed`: Phúc Âm Peter), 37 đoạn, ~1.352 từ (≈ 7 phút `edge_en`), 33 ảnh Baroque có sẵn. Đã chạy `create` trên backend tạm: kịch bản qua kiểm tra nguồn.
- Đã bỏ khỏi bản cũ các ý không cắt được nguồn: mốc năm 20/34/36, "43 năm" (thành "khoảng bốn thập kỷ"), "ornament of all Galilee" (Josephus viết "security of all Galilee"), đày sang Tây Ban Nha (Jewish War, chưa lấy nguồn), cách giải thích Pilate xâm phạm lãnh thổ (nay ghi rõ là phỏng đoán).
- **Ảnh tập 1–5 đã biến mất khỏi thư mục làm việc** (không do công cụ này). Các ảnh dùng lại đã cứu từ thư viện app của dự án #2/#4 vào `vox/pool_recovered/` (10 ảnh); spec tập 6/7/8 trỏ tới đó. Ảnh tập 3/2 (`ep3_034`, `ep3_036`, `ep2_007`) không cứu được nên tập 8 dùng ảnh khác thay.

## Tập 9 trở đi
Copy `ep6.spec.json` làm khuôn: đổi nguồn (`fetch` kiểu `bible`/`wikisource`/`wikipedia`), claims, kịch bản (kết bằng câu outro cố định: *If you made it this far, subscribe. A new figure from history every week.*), `scene_overrides`, ảnh. Ảnh tạo từ CSV (`_tools/bf.py prompts`/ hoặc prompt trong `vox/poster_test/STYLE.md`); chữ trên màn hình do code vẽ, không nhúng chữ vào ảnh.

## Bài học (đừng lặp lại)
- Không tự đổi phong cách chốt (collage). `cinematic`/`poster` đã bỏ khỏi UI.
- Preset dữ liệu (timeline/evidence/headline) cho tiếng Anh phải **viết tay** `scene_overrides`; bộ luật tự dò chữ viết cho tiếng Việt.
- Preview thử nghiệm chỉ nên 30–70 giây (`seconds`), không render đủ tập.
- Trích dẫn phải cắt từ nguồn thật (`fetch`), bỏ chi tiết không có nguồn ("months later", pháo đài Machaerus…).
