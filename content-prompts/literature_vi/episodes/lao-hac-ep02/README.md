# Lão Hạc — tập 2 (tác phẩm thứ hai của kênh văn học, theo chuẩn 14-16 phút)

Tác phẩm độc lập, dùng lại đúng khung `../../CHANNEL.md`, `VISUAL.md`, `SCRIPT_TEMPLATE.md`, `MAPPING.md`. Tác phẩm khác copy `../_TEMPLATE/`.

- **Mục tiêu tập:** giúp người chưa đọc Lão Hạc hiểu vì sao một người gần như chẳng còn gì để mất vẫn chọn cách chết đau đớn nhất, thay vì sống nhờ, sống gian, hay chỉ cần tiêu bớt số tiền đã dành sẵn cho con.
- **Câu hỏi trung tâm (giả thuyết):** vì sao lương thiện, với Lão Hạc, phải trả bằng một cái chết?
- **Góc nhìn đề xuất (chờ chủ kênh chốt):** mọi con đường để Lão Hạc tiếp tục sống — nhận giúp của ông giáo, làm liều kiểu Binh Tư, hay ăn vào tiền để lại cho con — đều phải đổi bằng đúng cái lão không chịu mất: tay sạch, không nợ, không lừa ai thêm lần nào nữa. Có cách đọc khác (không phải cao thượng, mà là dấu hiệu một hoàn cảnh đã hẹp đến mức người tốt nhất chỉ còn một cửa để đi) — kịch bản nêu cả hai, không chọn hẳn một bên.
- **Khán giả:** người chưa đọc truyện, học sinh, người lớn quan tâm tâm lý xã hội — đã xem hoặc chưa xem tập Chí Phèo đều xem được (có 2-3 chỗ đối chiếu nhẹ với Chí Phèo nhưng không bắt buộc phải xem tập 1 trước).
- **Thumbnail:** nền màu nâu đất/kraft, [Lao Hac CAST] mặt già khắc khổ nhìn xuống con chó vàng, chữ ≤ 4 từ ("AI HIỂU LÃO HẠC?" hoặc "CHẾT ĐỂ GIỮ LƯƠNG THIỆN"); chữ do người làm đặt.
- **Shorts gợi ý (25–30 giây):** (1) cảnh bán chó — "già bằng này tuổi đầu rồi còn đánh lừa một con chó"; (2) đoạn "Chao ôi! Đối với những người ở quanh ta..."; (3) khoảnh khắc ấm nhất — khoai lang và nước chè; (4) cái chết chỉ hai người hiểu — twist Binh Tư và bả chó.
- **Âm thanh gợi ý:** tiếng điếu cày, tiếng chó sủa rồi im bặt lúc bị bắt, một nhịp lặng trước câu "Chỉ có tôi với binh Tư hiểu"; không nhạc nền (hoặc rất nhỏ).
- **Câu hỏi cuối cho khán giả:** có sẵn ở đoạn cuối của `script.md`.

## Vì sao chọn Lão Hạc cho tập 2

Tập 1 (Chí Phèo) kể một người bị *người khác* chặn đường trở lại làm người lương thiện. Lão Hạc cho một đối trọng trong cùng tác giả: một người *tự khóa* đường của chính mình để giữ lương thiện, không ai ép ông cả — hai mặt của cùng một chữ, tạo một cặp tập hợp lý để mở đầu chuỗi nhiều tác phẩm của kênh. Truyện ngắn hơn Chí Phèo (không có cấu trúc nhiều thập niên/nhiều cánh bè làng), nên bản kịch bản này chủ động bổ sung các đoạn ít được trích (gốc khu vườn, kế hoạch dành dụm, kinh tế làng, cảnh khoai lang-nước chè, tả ngoại hình lúc khóc) để vừa giữ đúng chuẩn 14–16 phút, vừa không lặp ý hay thêm triết lý sáo rỗng.

## Kiểm chứng đã làm / còn lại

- Văn bản truyện lấy từ Wikisource tiếng Việt (trang "Lão Hạc"); **toàn bộ 29 nguồn / mọi needle** được kiểm bằng hàm `excerpt()` thật của `episode_builder.py` trước khi đưa vào spec (không chỉ kiểm `in text` thô — đã phát hiện và sửa vài needle gộp hai câu khiến hàm rơi về nguyên đoạn dài do cách chia câu theo `". "`; xem ghi chú trong `docs/features/`).
- **Đã chạy thật** `episode_builder.py create` hai lần trên backend tạm (SQLite scratch, cổng 8079, không đụng `backend/data/library.db` thật): lần đầu (bản 49 đoạn/2.226 từ) và lần sau khi mở rộng (bản cuối **62 đoạn / 3.149 từ**, project 2) — cả hai lần `script review: OK`, đủ 7 `kind`.
- **Đo thời lượng bằng audio thật, độc lập ngoài app** (`edge-tts` gọi trực tiếp thư viện `edge_tts`, giọng `vi-VN-NamMinhNeural`, chia theo từng đoạn lời đọc, thử lại tối đa 4 lần mỗi đoạn khi gặp lỗi `NoAudioReceived` ngẫu nhiên, đo bằng `ffprobe`, cộng lại — không qua app, không qua cổng):
  - Bản 49 đoạn (trước khi mở rộng): 46/49 đoạn đo được, 567,1s / 2.094 từ → tốc độ đo được **≈ 221,6 từ/phút**; suy ra cả 49 đoạn (2.226 từ) ước khoảng **~10 phút** — ngắn hơn chuẩn 14–16 phút của kênh.
  - Vì vậy đã **mở rộng kịch bản bằng nội dung có thật** (không lặp ý, không triết lý sáo rỗng): thêm 5 nguồn mới từ chính văn bản chưa dùng (gốc khu vườn do vợ lão dành dụm; kế hoạch bòn vườn để dành cho con; kinh tế làng mất nghề vè sợi sau bão; tả ngoại hình lúc lão khóc; cảnh khoai lang–nước chè) và khoảng 10 đoạn bình luận/diễn giải phân tích sâu hơn (toán kinh tế 200 đồng cheo cưới so với 30 đồng dành dụm; chó là vật thay con; tính toán pháp lý của văn tự; logic từ chối giúp đỡ; điểm mù tâm lý của người kể; so sánh cách chết ồn ào/âm thầm với Chí Phèo).
  - **Kết quả đo lại (bản cuối, 62 đoạn / 3.149 từ):** 59/62 đoạn đo liền mạch, 3 đoạn gặp `NoAudioReceived` ngẫu nhiên và đã đo lại riêng từng đoạn (một đoạn phải thử đến lần thứ 5). Tổng cộng toàn bộ 62 đoạn, **0 đoạn lỗi sau khi thử lại**: **843,3 giây = 14 phút 05 giây**, tốc độ đo được **≈ 224,1 từ/phút**. Nằm trong khoảng mục tiêu 14–16 phút, gần biên dưới (giống tình huống của tập Chí Phèo ở 14 phút 14 giây) nên không cần cắt.
- Đoạn BÌNH LUẬN là **bản nháp** do AI viết; chủ kênh viết lại bằng giọng của mình trước cổng 2.
- Claim `cause_interpretation` đánh dấu `disputed`: Nam Cao không viết thẳng "lão tự ăn bả chó mà chết"; đây là suy luận được chấp nhận rộng rãi (nối hai chi tiết: lão xin bả chó, và chỉ ông giáo với Binh Tư hiểu), không phải câu chữ trực tiếp — không khẳng định như sự kiện chắc chắn trong lời đọc.
- Chi tiết lịch sử "mộ phu đồn điền cao su" được nêu như bối cảnh thời đại nhưng **chưa có nguồn riêng** trong tập này (nằm ngoài văn bản Lão Hạc); nếu muốn khẳng định mạnh hơn (số liệu, điều kiện lao động) cần dẫn nguồn lịch sử độc lập trước khi đăng.
- Cần đối chiếu một bản in (chính tả cũ/hiện đại, văn bản Wikisource có thể khác bản nhà xuất bản).
- `image_prompts.csv`/`.md` **chưa tạo** cho tập này — số cảnh/ảnh thật chỉ có sau khi chạy `storyboard` (cần duyệt gate 1–2 trước, đúng theo state machine, chưa tự duyệt).
- Việc nhỏ cần làm khi chạy lần đầu của kênh (đã ghi trong tập 1, vẫn chưa làm): kiểm thử dấu tiếng Việt của chữ cắt dán trong theme collage.

## Chạy

```
python content-prompts/vox_documentary_template/tools/episode_builder.py create content-prompts/literature_vi/episodes/lao-hac-ep02/spec.json
```

(backend chạy từ thư mục tạm, biến môi trường `APP_DATABASE_URL`/`APP_LIBRARY_DIR` chỉ vào thư mục tạm, `DOC_API` chỉ vào cổng backend tạm — không bật `.env` thật, không đụng DB thật). Sau đó duyệt cổng 1–2 trong app (DB thật), `storyboard`, thêm `scene_overrides`/`images` (xuất CSV mới trước), giọng `edge` tiếng Việt, render **collage** (tắt ảnh đen trắng).

Đo lại thời lượng độc lập (không qua app) bất cứ khi nào sửa lời đọc:
```
cd backend && .venv/Scripts/python.exe -m edge_tts --voice vi-VN-NamMinhNeural --file <lời-đọc-thuần.txt> --write-media <scratch>/draft.mp3
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 <scratch>/draft.mp3
```
Nếu gặp `NoAudioReceived` (ngẫu nhiên, đã biết), chia theo đoạn/cảnh và thử lại từng đoạn, cộng thời lượng lại.

## Cách bắt đầu tập 3 từ đây

Copy `../_TEMPLATE/` cho một tác phẩm khác (ví dụ "Vợ nhặt", "Vợ chồng A Phủ" — chưa chọn, chờ chủ kênh), fetch văn bản thật từ Wikisource tiếng Việt, viết `characters.md`/`script.md` theo đúng khuôn 5 nhóm biên tập → 7 `kind`, kiểm từng needle bằng hàm `excerpt()` thật trước khi ghi vào spec (tránh needle gộp hai câu — xem bài học ở trên), rồi chạy `create` trên backend tạm và đo thời lượng bằng `edge-tts` độc lập trước khi báo xong.
