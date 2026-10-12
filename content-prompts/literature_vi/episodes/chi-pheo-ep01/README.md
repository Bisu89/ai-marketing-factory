# Chí Phèo — tập 1 (ví dụ minh họa template kênh văn học, refactor ~15 phút)

Đây là **một ví dụ** để kiểm chứng template (`../../CHANNEL.md`, `VISUAL.md`, `SCRIPT_TEMPLATE.md`, `MAPPING.md`); tác phẩm khác copy `../_TEMPLATE/`.
Refactor 2026-10-12: mở rộng từ ~9 phút/36 đoạn lên **~15 phút/49 đoạn**, theo chuẩn thời lượng mới của kênh (`SCRIPT_TEMPLATE.md`).

- **Mục tiêu tập:** giúp người chưa đọc Chí Phèo hiểu vì sao điều nhỏ nhất hắn xin (được lương thiện) lại không thể có.
- **Câu hỏi trung tâm (giả thuyết):** vì sao mong muốn trở lại cuộc sống bình thường, tử tế của Chí Phèo trở thành bi kịch?
- **Góc nhìn đề xuất (chờ chủ kênh chốt):** "lương thiện" cần được người khác công nhận; cả Bá Kiến, bà cô lẫn vết sẹo đều chặn điều đó. Bản refactor thêm một lớp: Chí Phèo không phải trường hợp cá biệt mà là người thứ ba trong một chuỗi "đầu bò" (Năm Thọ → binh Chức → Chí Phèo) mà Bá Kiến cần để giữ làng — giết Bá Kiến không giết được cơ chế đó. Có cách đọc khác (trách nhiệm cá nhân) và kịch bản nêu cả hai.
- **Khán giả:** người chưa đọc truyện, học sinh, người lớn quan tâm tâm lý xã hội.
- **Thumbnail:** nền màu phẳng đỏ gạch, [Chi Pheo CAST] mặt lớn bên phải nhìn thẳng, 1/3 trái tối chừa chỗ chữ ≤ 4 từ ("AI CHO TAO LƯƠNG THIỆN?"); chữ do người làm đặt.
- **Shorts gợi ý (25–30 giây):** (1) bát cháo hành: "người ta hay hối hận khi không đủ sức mà ác nữa"; (2) câu hỏi "Ai cho tao lương thiện?"; (3) Năm Thọ — binh Chức — Chí Phèo: ba người, một vai trò; (4) vì sao lò gạch ở đầu và cuối truyện.
- **Âm thanh gợi ý:** tiếng chai vỡ, gió ruộng, bát sứ chạm bàn, một nhịp lặng trước câu "Ai cho tao lương thiện"; không nhạc nền (hoặc rất nhỏ).
- **Câu hỏi cuối cho khán giả:** có sẵn ở đoạn cuối của kịch bản.

## Những gì mới trong bản refactor (so với bản ~9 phút cũ)
- Cấu trúc biên tập 5 phần (xem đầu `script.md`), map vào đúng 7 `kind` kỹ thuật (PHẦN 3 chia `timeline` + `evidence`, PHẦN 5 chia `consequences` + `conclusion`).
- Thêm chất liệu có thật từ văn bản (không bịa): hồi tưởng của Bá Kiến về Năm Thọ và binh Chức (hai "đầu bò" ông dùng trước Chí Phèo); cơ chế cánh bè làng Vũ Đại ("quần ngư tranh thực"); cảnh Bá Kiến xử nhũn gọi hắn vào nhà; tự Lãng (bạn rượu); cảnh gặp Thị Nở bên bờ sông; ký ức về bà ba năm hai mươi tuổi lúc ăn cháo hành; lời Đội Tảo và câu "tre già măng mọc" sau khi Bá Kiến chết; gợi ý mang thai của Thị Nở ở cuối truyện (giữ tính mở, đánh dấu `disputed` vì văn bản không xác nhận).
- 6 điểm GÓC NHÌN NHÂN VẬT (POV) rải theo đúng các mốc chuyển biến tâm lý: trở về làng, nhận ra chỗ đứng của mình, tỉnh rượu, đón bát cháo hành, hy vọng, đối diện sự từ chối.

## Kiểm chứng đã làm / còn lại
- Văn bản truyện lấy từ Wikisource tiếng Việt; **toàn bộ 23 nguồn / mọi needle** được `episode_builder.py` cắt nguyên văn từ trang thật — **0 lỗi** khi chạy `create` trên backend tạm (chạy hai lần trong quá trình mở rộng, lần cuối 2026-10-12).
- **Đã chạy thật** `episode_builder.py create` trên backend tạm (DB riêng, cổng 8077, SQLite scratch, không đụng `backend/data/library.db` thật, đã tắt tiến trình sau khi xong): project 3, **23 nguồn, 39 khẳng định**, kịch bản **60 đoạn / 2.929 từ**, qua `script review: OK` (chỉ có 1 warning thông tin: ước tính theo số chữ của backend dùng mục tiêu chung 480–600s của mọi dự án documentary, không phải chuẩn riêng 14–16 phút của kênh văn học — độ dài thật đo bằng audio thật, xem dưới).
- **Chưa** chạy `storyboard` (cần duyệt gate 1–2 trước, đúng theo state machine — không tự duyệt); vì vậy **chưa có số cảnh/ảnh thật**, chỉ ước tính ~35–45 theo `VISUAL.md` mục 6. `image_prompts.csv`/`.md` hiện tại **đã lỗi thời** (ứng với bản 9 phút/36 đoạn cũ) — xem cảnh báo trong `image_prompts.md`.
- **Đo thời lượng bằng audio thật, độc lập ngoài app** (`edge-tts` gọi trực tiếp thư viện `edge_tts`, giọng `vi-VN-NamMinhNeural`, chia theo từng đoạn lời đọc + thử lại khi gặp lỗi `NoAudioReceived` ngẫu nhiên, đo bằng `ffprobe`, cộng lại — không qua app, không qua cổng). Kết quả cuối (toàn bộ 60 đoạn, một lần đo liền, 0 đoạn lỗi): **854,3 giây = 14 phút 14 giây**, cho 2.929 từ lời đọc → tốc độ đo được **≈ 205,7 từ/phút** (nhanh hơn giả định cũ 130–150 từ/phút ghi trong `HANDOFF.md`/`SCRIPT_TEMPLATE.md` cũ — ghi nhận lại cho các tập sau). Nằm trong khoảng mục tiêu 14–16 phút, gần biên dưới nên không cần cắt.
  Đây là bước hiệu chỉnh kịch bản, không phải audio sản xuất chính thức (audio chính thức vẫn tạo trong app ở cổng 3→4, dùng giọng `edge` đã chọn cho kênh).
- Đoạn BÌNH LUẬN là **bản nháp** do AI viết; chủ kênh viết lại bằng giọng của mình trước cổng 2.
- Cần đối chiếu một bản in (chính tả cũ/hiện đại, văn bản Wikisource có thể khác bản nhà xuất bản). Đoạn gợi ý Thị Nở có thể mang thai ở cuối truyện giữ nguyên tính mở của văn bản (claim đánh dấu `disputed`), không khẳng định.
- Việc nhỏ cần làm khi chạy lần đầu: kiểm thử dấu tiếng Việt của chữ cắt dán trong theme collage (vẫn chưa làm).

## Chạy
```
python content-prompts/vox_documentary_template/tools/episode_builder.py create content-prompts/literature_vi/episodes/chi-pheo-ep01/spec.json
```
(backend chạy từ thư mục tạm, biến môi trường `APP_DATABASE_URL`/`APP_LIBRARY_DIR` chỉ vào thư mục tạm, `DOC_API` chỉ vào cổng backend tạm — không bật `.env` thật, không đụng DB thật). Sau đó duyệt cổng 1–2 trong app (DB thật), `storyboard`, thêm `scene_overrides`/`images` (xuất CSV mới trước, xem `image_prompts.md`), giọng `edge` tiếng Việt, render **collage** (tắt ảnh đen trắng).

Đo lại thời lượng độc lập (không qua app) bất cứ khi nào sửa lời đọc:
```
cd backend && .venv/Scripts/python.exe -m edge_tts --voice vi-VN-NamMinhNeural --file <lời-đọc-thuần.txt> --write-media <scratch>/draft.mp3
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 <scratch>/draft.mp3
```
Nếu gặp `NoAudioReceived` (ngẫu nhiên, đã biết trong `HANDOFF.md`), chia theo đoạn/cảnh và thử lại từng đoạn, cộng thời lượng lại — xem script mẫu trong báo cáo refactor.
