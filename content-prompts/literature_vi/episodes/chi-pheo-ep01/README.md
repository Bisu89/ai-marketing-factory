# Chí Phèo — tập 1 (ví dụ minh họa template kênh văn học, 14 phút 06 giây đo thật)

Đây là **một ví dụ** để kiểm chứng template (`../../CHANNEL.md`, `VISUAL.md`, `SCRIPT_TEMPLATE.md`, `MAPPING.md`); tác phẩm khác copy `../_TEMPLATE/`.
Refactor 2026-10-12: mở rộng từ ~9 phút/36 đoạn lên ~15 phút/49 đoạn. **Review cuối 2026-10-13** (theo yêu cầu chủ kênh): sửa hook, rút gọn phần cánh bè, gộp đoạn kết lặp ý, đối chiếu lại toàn bộ 23 nguồn bằng đúng hàm cắt trích đoạn thật — bản hiện tại **58 đoạn / 2.921 từ / 14 phút 06 giây đo bằng edge-tts thật**. Xem mục "Review cuối" dưới đây.

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

## Review cuối (2026-10-13, theo yêu cầu chủ kênh)

Review toàn bộ kịch bản và sửa trực tiếp `spec.json`/`script.md` (không viết lại từ đầu). Những phần được yêu cầu giữ đều còn nguyên: quá trình Chí bị Bá Kiến lợi dụng (còn thêm một đoạn mới làm rõ hơn — xem mục 1 dưới), Năm Thọ/binh Chức làm bằng chứng cho sự lặp lại của hệ thống, bát cháo hành và diễn biến tâm lý của Chí, góc nhìn cân bằng xã hội/cá nhân ở kết, và hình ảnh lò gạch cũ.

**1. Hook không còn tiết lộ sớm.** Câu "tao muốn làm người lương thiện" trước đây xuất hiện ở đoạn 2 của hook; nay hook chỉ tease ("một điều không ai, kể cả hắn, từng nghĩ hắn còn có thể muốn") và câu nói thật chỉ xuất hiện đúng chỗ ở Phần 5 (I), lúc cao trào.

**2. Rút gọn phần cánh bè.** Đoạn liệt kê "cánh cụ bá, cánh Đội Tảo, cánh tư Đạm, cánh bát Tùng" + ẩn dụ "miếng mồi chung" được rút ngắn, chỉ còn cánh cụ bá và cánh Đội Tảo (nhân vật này quay lại ở Phần 5 nên giữ). Năm Thọ/binh Chức giữ nguyên đầy đủ, không đụng.

**3. Giảm câu bình luận sáo rỗng/đối xứng.** Cắt: "Một người không tuổi, không tên trong sổ, thì khó mà được công nhận là người, trước khi nói đến lương thiện" (giữ lại phần sự kiện, bỏ phần khẩu hiệu); cắt hẳn đoạn "Nhưng được sợ không phải là được coi là người. Và ai hưởng lợi từ cái sợ ấy, thì chắc chắn không phải là Chí Phèo" (ý này được phát biểu một lần, rõ hơn, ở đoạn kết thay vì lặp ở đây); viết lại câu "Hai lần có đàn bà trong đời hắn: một lần để bị dùng, một lần để được cho. Khác nhau đúng một chỗ — ai coi hắn là người" (cấu trúc đối xứng) thành câu cụ thể hơn, bớt vần vè.

**4. Gộp 6 đoạn kết thành 4, bỏ lặp ý.** Ba đoạn cũ (bi kịch cá nhân/lương thiện cần công nhận; chuỗi Năm Thọ-binh Chức-Chí Phèo; "đọc bằng ngôn ngữ hôm nay... mô hình quen") gộp thành một đoạn tiến triển; giữ nguyên đoạn "cách đọc khác — chính Chí Phèo là người cầm dao" và câu hỏi mở.

**5-6. Đối chiếu từng trích dẫn bằng hàm `excerpt()` thật** (không chỉ xem nhãn `claims`/`open`/`wish`/`porridge` có tồn tại). Phát hiện và sửa:
- **Lỗi kỹ thuật** (đã có từ bản cũ, không phải do review lần này gây ra): needle gộp 2 câu khiến hàm cắt trích đoạn rơi về nguyên cả đoạn dài, gây trích đoạn lặp/thừa ở 6 nguồn: `open`, `bakien`, `factions`, `drunk`, `thino`, `awake`. Đã tách mỗi needle về đúng 1 câu; ghi bài học vào `MAPPING.md`.
- **Thiếu nguồn cho chi tiết có thật**: "một cái tát... tiếng đấm đá nhau" (gate), hai giả thuyết về lý do Chí vào tù (prison), tuổi 50 của bà cô (bacô), tiểu sử tự Lãng — vợ chết, con gái chửa hoang bỏ đi (tulang) — tất cả đều **có thật trong văn bản**, chỉ là trước đây chưa có needle trích đúng câu; đã thêm needle, đối chiếu sạch.
- **Một chi tiết sai bị sửa**: script ghi Thị Nở "có phần ngẩn ngơ" — chữ này **không có trong văn bản**; chữ Nam Cao dùng là "dở hơi". Đã sửa lại đúng nguyên văn.
- **Một chi tiết thiếu bị bổ sung**: "trần truồng" (thiếu chi tiết "quấn trong một cái váy đụp" khi được nhặt).
- **Không tìm thấy khẳng định nào phải hạ xuống diễn giải** — mọi câu còn lại (kể cả "xứng đôi, nhất định lấy nhau", "tiếng đấm đá nhau bình bịch") sau khi tra lại đều khớp nguyên văn, chỉ là trước đây thiếu needle backing, không phải bịa.

**7. Ba loại nội dung vẫn tách bạch** theo 3 nhãn `[NGƯỜI KỂ]` / `[GÓC NHÌN NHÂN VẬT]` / `[BÌNH LUẬN CỦA CHỦ KÊNH]` trong `script.md`; không có thay đổi cấu trúc lớn, chỉ sửa nội dung từng đoạn.

**8. Overclaim về động cơ/quan hệ:** kiểm tra riêng "pair"/"xứng đôi" (Chí–Thị Nở) và "auntbg" (ý nghĩa của bà cô) — cả hai đều khớp nguyên văn khi đối chiếu kỹ (claim "auntbg" nay có needle riêng cho chi tiết tuổi 50, trước đây thiếu). "prison" (lý do Chí vào tù) đã đúng là `disputed` từ bản cũ, không đổi.

**9-10. Thời lượng đo bằng audio thật, không ước lượng.** Sau khi sửa (56 đoạn), đo được **13 phút 46 giây** — ngắn hơn biên dưới 14 phút khoảng 14 giây. Thêm đúng 3 đoạn nội dung thật chưa dùng (không lặp câu, không đọc chậm giả tạo): câu thật "Chí Phèo ra về... vô cùng hể hả" (đã có nguồn, trước đây chưa dùng) + một câu bình luận ngắn làm rõ hơn trọng tâm "bị lợi dụng" (đúng mục 1 chủ kênh muốn giữ) + sửa chi tiết tự Lãng cho đúng và đủ hơn. Đo lại 3 đoạn này bằng edge-tts/ffprobe độc lập, cộng vào tổng cũ: **845,8 giây = 14 phút 06 giây**, tốc độ đo được ≈ 206,8 từ/phút. Trong khoảng mục tiêu 14–16 phút.

Đã chạy lại `episode_builder.py create` hai lần trên backend tạm (cổng 8081 rồi 8082, SQLite scratch, không đụng DB thật) với bản cuối: **script review: OK** cả hai lần.

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
