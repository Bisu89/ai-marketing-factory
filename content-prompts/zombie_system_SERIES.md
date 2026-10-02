# Zombie System — hồ sơ series

Fiction serial webtoon-recap: zombie apocalypse học đường + hệ thống LitRPG ẩn (status window /
level / skill / quest) mà chỉ nhân vật chính nhìn thấy — bắt trend "system apocalypse" đang thịnh
trên các kênh recap webtoon. **VI + KR only, không làm bản tiếng Anh** (quyết định rõ ràng: "tiếng
anh thì không hợp manhwa lắm"). Template `zombie_system` trong `backend/app/modules/beat/schemas.py`
(built-in #10, series fiction gốc đầu tiên — không phải recap truyện có sẵn).

Toàn bộ script gốc (nguồn sự thật, đọc cái này thay vì suy luận lại cốt truyện từ trí nhớ) nằm ở
[`zombie_system_scripts/epN_script.txt`](zombie_system_scripts/). Prompt ảnh từng tập nằm ở
`zombie_system_epN_scenes.csv` + ảnh đã tạo trong `zombie_system_epN_images/`.

## Format & công thức kênh

- Mỗi tập là một chương truyện (~1800-2100 từ tiếng Việt/Hàn/nguồn), không phải tóm tắt — đây là
  **truyện gốc do AI + người dùng viết**, không chuyển thể từ webtoon có sẵn.
- Dựng bằng `visual_generation.mode="library"`: một pool ảnh nhỏ tái sử dụng mỗi tập (~$0 chi phí
  biên) thay vì AI-generate theo từng beat — người dùng tự tạo ảnh tay qua ChatGPT từ CSV prompt rồi
  import vào Asset Library.
- Không nhạc nền (quyết định cố định, đã bake thẳng vào default của Template từ Chương 8 — xem mục
  "Sự cố thật" bên dưới).
- Giọng đọc: `edge_tts` (free), giọng nữ `vi-VN-HoaiMyNeural` (VI) / giọng tương ứng cho KO.

## Phong cách hình ảnh + quy tắc an toàn nội dung (áp dụng cho MỌI prompt mới)

- **Style**: Korean webtoon / manhwa, bold clean black ink linework, flat 2D cel-shaded coloring,
  hard-edged shadow shapes, màu bão hoà rực — **tuyệt đối KHÔNG** painterly / semi-realistic anime /
  photorealistic / 3D render. Máu luôn là **ichor đen/sẫm màu mỏng**, không bao giờ đỏ (đọc như "bị
  nhiễm/hỏng" chứ không phải gore thật — an toàn hơn cho monetization).
- **Kỹ thuật negative-prompt** (từ Tập 4 trở đi, đã chứng minh hiệu quả): luôn thêm khối
  `NEGATIVE PROMPT: ...` tường minh (lỗi giải phẫu, khoả thân, painterly/photorealistic, máu đỏ,
  text/watermark) vào mọi prompt ảnh, không chỉ mô tả bằng lời. Dùng thêm biến thể
  `NEGATIVE_ADULTS_ONLY` ("child, teenager, youthful-looking character") **chỉ** cho cảnh không có
  nhân vật vị thành niên nào xuất hiện.
- **Quy tắc cứng, không có ngoại lệ**: không tạo dáng gợi cảm/sexy cho nhân vật được viết là vị
  thành niên (Jaehyun, Mira, Soomin = 17 tuổi; bé gái = 7-8 tuổi), bất kể prompt diễn đạt thế nào.
  Phong cách "quyến rũ/gợi cảm" chỉ dành cho nhân vật người lớn tường minh (Cô Yoon, Y tá Han,
  Soyeon, Trung sĩ Yuri) — luôn giữ ở mức tinh tế/không khoả thân (không lộ ngực, không tư thế gợi
  dục) kể cả khi outfit được yêu cầu táo bạo hơn (áo crop top của Yuri).
- Tránh gọi tên vũ khí thật cụ thể trong prompt ("sidearm holstered" từng bị ChatGPT từ chối vì vi
  phạm chính sách nội dung) — mô tả chung chung ("tactical belt with pouches") thay thế.
- Mỗi nhân vật tái diễn có một khối mô tả nhận diện cố định, copy y nguyên qua từng tập — không vẽ
  lại mặt/trang phục khác đi giữa các chương.

## Kỹ thuật sản xuất học được qua thực tế

- **Tiếng Hàn: phương pháp viết an toàn bắt buộc**. Gõ thẳng câu KO dài/phức tạp vào code **âm thầm
  làm hỏng chữ** (thay ngẫu nhiên ký tự Hangul, lẫn ký tự lạ) — phát hiện ở Tập 5. Luôn: ghi câu KO
  ngắn vào file check đánh số (`epN_ko_check.txt`, dạng `NN|câu`), đọc lại bằng tool Read để soát lỗi
  (quét ký tự ngoài vùng Hangul), rồi mới ghép bằng code vào beat. Không bao giờ gõ thẳng một đoạn KO
  dài nhiều mệnh đề vào một list literal lớn.
- **Trần Beat.duration ≤ 120.0s** — ước lượng `dur()` của app dùng wps thận trọng (KO 2.3, VI 2.35);
  một beat ôm nguyên cả cảnh nhiều đoạn sẽ fail validate. Tốc độ đọc thật đo được nhanh hơn nhiều:
  **KO ~1.8 từ/giây, VI ~3.6 từ/giây** (tiếng Việt đơn âm tiết nên đếm từ nhanh) — dùng số này để dự
  đoán thời lượng video thật, không dùng hằng số nội bộ của app.
- Số ảnh mới mỗi tập tăng theo diễn biến truyện (6 → 10 → 25 → 18 → 16...), luôn theo nhu cầu nội
  dung thật (nhân vật/bối cảnh/beat hành động mới), không bơm/giảm giả tạo.
- **Từ Chương 8**: đổi quy trình viết — kịch bản **viết gốc bằng tiếng Việt**, không viết tiếng Anh
  rồi dịch nữa. Tiếng Anh không còn cần thiết cho quy trình sản xuất.

## Dàn nhân vật cố định

| Nhân vật | Tuổi/vai trò | Xuất hiện | Ghi chú |
|---|---|---|---|
| **Jaehyun** | 17, nam chính, giữ Hệ Thống ẩn | Tập 1 | Kỹ năng lõi: Danger-sense + Adrenaline Edge (mở khoá T3); từ T8 Hệ Thống không còn cảnh báo "có thể không đủ" nữa — kỹ năng chạy mượt thật sự. Dùng gậy bóng chày nhôm của Doyun từ T4. |
| **Mira** | 17, bạn học | Tập 1 | Bình tĩnh, vững vàng dưới áp lực. |
| **Soomin** | 17, bạn học | Tập 1 | Nhân vật phụ (mới chỉ xuất hiện T1). |
| **Cô Yoon** | đầu 30, giáo viên chủ nhiệm | Tập 1 (kẹt T2) | Mắc kẹt khu giảng viên từ T2, được cứu T5, đi cùng nhóm từ đó. |
| **Y tá Han** | 27, y tá trường | Tập 2 | Ngày càng bộc lộ là chiến binh thật sự, không chỉ y tá (dùng rìu cứu hoả chiến đấu T5-6). |
| **Doyun** | giữa 30, trưởng nhóm sống sót thứ hai | Tập 3 (gặp), T4 (liên minh) | Đưa Jaehyun cây gậy; giờ chiến đấu bằng súng trường nhặt được. |
| **Soyeon** | cuối 20, nhóm Doyun | Tập 4 | Cựu HLV tự vệ, đồ sinh tồn thực dụng/thời trang. Quy tắc cố định: **nữ chiến binh người lớn chỉ bị thương nhẹ/rách quần áo khi chiến đấu, không bao giờ bị cắn** — Soyeon luôn dính đòn (T6, T8) nhưng luôn toàn vẹn. |
| **Cậu thiếu niên bị thương** & **người đàn ông to con ("sleeping man")** | nhóm Doyun | T4 | **Cả hai bị cắn và hoá zombie ở Chương 6** (người đàn ông chết khi che chắn Jaehyun khỏi con zombie thông minh) — bị bỏ lại ở trường. Nhánh đau buồn chưa giải quyết, đặc biệt với bé gái. |
| **Bé gái** | 7-8 tuổi | T4 | Từng gắn bó với người đàn ông to con, mồ côi lần nữa sau T6. Không bao giờ tạo hình gợi cảm/khác tuổi thật. |
| **Con zombie thông minh** | phản diện tái diễn | T2 (thấy lần đầu) | Hệ Thống xác nhận nó "đang bám theo đặc biệt" Jaehyun (T5), dàn dựng cuộc phục kích sân trường T6, bị đẩy lùi và rút vào bóng tối (T6) — **chưa chết, chưa giải quyết, chưa rõ tung tích** tính đến T8. Giữ hành vi xa lạ/khó đọc như người, không nhân hoá cảm xúc (một bản nháp mô tả nó "bực bội" từng bị bác bỏ vì quá giống con người). |
| **Trung sĩ Baek** | 40s, chỉ huy trạm gác | Tập 7 | Tóc hoa râm, chỉ huy tiền đồn nhỏ. |
| **Lính trẻ** | cuối teen/đầu 20 | Tập 7 | Kiểm tra nhóm ở cổng, mềm lòng với bé gái. |
| **Quân y** | cuối 20 | Tập 7 | |
| **Trung sĩ Yuri** | cuối 20 | Tập 7 | Tóc ngắn bạch kim, găng hở ngón, áo tactical crop top sát nách — chiến binh mạnh nhất xuất hiện trong series tính đến giờ, toả sáng trong trận đánh T8. |

## Tóm tắt cốt truyện qua từng tập

**T1**: dịch zombie bùng giữa giờ học; Jaehyun nhận Hệ Thống, cứu Soomin, cố thủ cùng Mira.
**T2**: Y tá Han chạy vào bị thương, báo tin Cô Yoon kẹt tầng 3 khu giảng viên; lần đầu thấy con
zombie thông minh đứng bất động lạ thường giữa đàn đang lảo đảo.
**T3**: một nỗ lực giải cứu biến thành phục kích; Adrenaline Edge mở khoá; cliffhanger lộ ra nhóm của
Doyun sau cánh cửa cố thủ.
**T4**: hai nhóm liên minh thận trọng; Doyun đưa Jaehyun cây gậy; cơ chế "Reputation" xuất hiện.
**T5**: nhiệm vụ giải cứu chung cứu được Cô Yoon sau một trận chiến thật; tìm thấy mảnh giấy ghi chú
nửa mờ ("đã xác nhận dịch bệnh... không mở cổng cho đến khi..."); con zombie thông minh đối đầu trực
tiếp trên cầu thang, bám theo đích danh Jaehyun.
**T6**: đường rút bị chặn (không phải tình cờ), đẩy cả nhóm vào giữa trận chiến của đội nghi binh đã
quá tải; con zombie thông minh săn Jaehyun giữa hỗn loạn; cậu thiếu niên bị thương và người đàn ông
to con đều bị cắn và hoá (người sau che chắn Jaehyun), bị bỏ lại; Soyeon tiết lộ kế hoạch thật luôn
là một "cổng" ở hàng rào phía đông; chương kết với cả nhóm bị đèn pha trạm gác rọi trúng, bị lệnh
đứng im.
**T7**: trạm gác hoá ra chỉ là một tổ lính gần như bỏ hoang, không phải cuộc giải cứu lớn như hy
vọng — điểm sơ tán thật là một sân vận động cách 11km, liên lạc radio chập chờn; một cảnh nghỉ/thở
(khoảnh khắc yên bình đầu tiên cả series); Trung sĩ Yuri xuất hiện; còi báo động vang lên báo một đàn
zombie khổng lồ đang dồn về phía đèn pha trạm gác, kết ở "Giữ vị trí."
**T8**: trận đánh với đàn zombie — kỹ năng chiến đấu của Yuri toả sáng, đạn cạn dần, Jaehyun cứu bé
gái bằng một lần dùng Adrenaline Edge trơn tru (Hệ Thống không còn dè dặt nữa); chiếc xe duy nhất (8
chỗ, vốn đã không đủ cho cả nhóm gộp lại) hư hỏng, cần sửa hơn một tiếng; giữ được đợt sóng, không ai
chết — nhưng kết thúc bằng một bí ẩn mới: Trung sĩ Baek bắt được một tín hiệu radio nhiễu sóng lạ,
một giọng nói không rõ danh tính chỉ nói "Chúng chưa biến mất đâu" rồi mất sóng thành tiếng rè.

**T9 "Tám Chỗ Ngồi"** (script + 21 ảnh + VI + KO render xong; KO nguồn: `zombie_system_scripts/ep9_ko_check.txt`): chờ sửa xe; bài toán 11 người / 8 ghế —
Baek ra lệnh 7 dân thường + Kang lái, Yuri cãi lệnh và giành chỗ; cuối cùng 9 người nhồi vào xe 8 chỗ
(bé gái ngồi lòng Cô Yoon), Baek + quân y ở lại trạm; bé gái ôm chiếc mũ len xám của người đàn ông to
con, Jaehyun ngồi cạnh an ủi (để tang T6); con zombie thông minh xuất hiện đứng quan sát ở rìa cây rồi
quay đi về hướng đông (không nhân hoá, không vội); radio sân vận động cuối cùng trả lời đúng mật hiệu
("mất điện 3 tiếng"), Baek hỏi về đoạn đường phía đông nhưng không nói ra điều mình thấy; kết: Hệ Thống
báo "Mục tiêu theo dõi... vị trí: phía trước" và nó đứng giữa đường nhựa chắn xe. Nhân vật mới: **Binh
nhì Kang** (chính là "lính trẻ" T7-8, giờ có tên, thuộc đường đi sân vận động). Giọng radio bí ẩn T8 để
mở tiếp, chưa giải thích.

## Nhánh truyện còn mở cho Tập 9 (đã xử lý một phần ở T9 — xem trên; còn lại cho T10)

- Xe hỏng chỉ chở được 8 người; nhóm gộp lại đã đông hơn thế và chưa ai bàn ai được lên xe.
- Giọng nói radio bí ẩn ("Chúng chưa biến mất đâu") — cố tình để mơ hồ giữa đàn zombie / con zombie
  thông minh / điều gì đó khác hẳn; chưa giải thích.
- Vị trí/ý định hiện tại của con zombie thông minh vẫn chưa rõ từ sau khi nó rút lui ở T6.
- Điểm sơ tán sân vận động (11km về đông) chưa đến được, chưa có xác nhận radio nào kể từ lúc trời
  tối.
- Hai mất mát ở T6 (cậu thiếu niên, người đàn ông to con) chưa được để tang trên màn hình — đặc biệt
  là phản ứng của bé gái.

## Trạng thái sản xuất

Tất cả project dưới đây đã **render xong, QA PASS**. ID tra theo tên qua `GET /api/v1/projects/{id}`
(không liên tục theo số thứ tự chương — xen kẽ với project của niche khác trong cùng DB).

| Tập | Project VI | Project KO | Ghi chú |
|---|---|---|---|
| 1 | 95 | 94 (+ 93 bản EN cũ, không dùng) | |
| 2 | 97 | 96 | |
| 3 | 99 | 98 | |
| 4 | 101 | 100 | |
| 5 | 106 | 105 | project 103 (VI) là bản nháp bị bỏ, không có render |
| 6 | 108 | 107 | |
| 7 | 111 | 110 | |
| 8 | **133** (bản render được, sau nhiều lần retry) | 122 | Project 123 (VI) là 14+ lần thử thất bại ban đầu — xem "Sự cố thật" bên dưới |
| 9 | **153** (render job 212, QA PASS 100) | **154** (render job 213, QA PASS 100) | 21 ảnh mới; TTS fail 2 lần → `_MAX_TTS_SEGMENTS` 16→24 rồi OK; cần `continue?force=true` để qua NEEDS_REVIEW (cảnh báo BODY liên tiếp, vô hại) |
| Recap Short "Những Người Phụ Nữ Của Tận Thế" | 130 (54.85s) | 131 (56.38s, đã rút gọn khớp nhịp VI) | Tổng hợp cảnh hành động của Han/Soyeon/Mira/Yuri, 9:16, word_pop caption, không nhạc nền |

## Vị trí tài liệu

- **Script gốc từng tập**: `zombie_system_scripts/epN_script.txt` — nguồn sự thật, đọc cái này thay
  vì suy luận lại cốt truyện khi bắt đầu phiên làm việc mới hoặc viết tập tiếp theo.
- **Title/description/thumbnail prompt (T1-8)**:
  `backend/data/library/_video_composer/New folder/zombie_system_titles_descriptions_ep1-8.txt`
- **CSV ảnh mới + thư mục ảnh từng tập**: `zombie_system_epN_scenes.csv` + `zombie_system_epN_images/`
- **Recap Short**: `zombie_system_recap_short_script.txt` + `zombie_system_recap_short_scenes.csv` +
  `zombie_system_recap_short_images/`
- Script build/register/dịch là scratchpad-only (không nằm trong repo) — nếu bắt đầu lại từ đầu, dựng
  lại quy trình từ CSV + script ở trên thay vì tìm file scratchpad cũ.

## Sự cố thật đã gặp (để tránh lặp lại)

- **Nhạc nền mặc định**: Template `zombie_system` từng mặc định `music_enabled=True`, trong khi mọi
  tập thật đều phải tắt tay. Đã sửa thẳng default trong Template (Chương 8) để không cần override mỗi
  tập nữa.
- **Saga TTS Chương 8 (VI)** — sự cố thật dài nhất của series, 14+ lần thử thất bại qua nhiều giờ và
  một ngày lịch: `edge_tts` (free, không chính thức) báo lỗi `NoAudioReceived` liên tục. Đã loại trừ
  lần lượt: nội dung/văn bản cụ thể, tổng số lượt gọi mạng, process rác còn sót, trạng thái project
  hỏng, phiên Claude khác tranh cổng. Manh mối thật: log server cho thấy **nhiều chuỗi retry độc lập
  chồng lấn thời gian thực** trong một lần chạy — do thread nền mồ côi từ các lần chạy bị ngắt trước
  đó vẫn gọi `edge_tts` song song dù mỗi lần chạy riêng lẻ vốn tuần tự. Sửa bằng
  `threading.Semaphore(2)` toàn tiến trình quanh mọi lệnh gọi `edge_tts` thật (file
  `backend/app/modules/voice/providers.py`). Sau khi sửa, lỗi *đổi dạng* chứ chưa hết: xác định thêm
  hai nguyên nhân thật khác — (1) `boundary="WordBoundary"` (cần cho caption khớp từng từ) tự nó làm
  tăng tỉ lệ lỗi của free endpoint, sửa bằng cách rơi về gọi không có word-boundary sau khi hết lượt
  retry thật; (2) **nguyên nhân gốc cuối cùng**: một đoạn gộp câu cụ thể (~1200 ký tự, nhiều câu ghép
  lại để giảm số lượt gọi mạng) có tỉ lệ lỗi cao bất thường so với các đoạn ngắn hơn cùng script/giọng
  — xác nhận bằng test trực tiếp lặp lại nhiều lần (15/15 lần thất bại trên đúng đoạn đó, trong khi
  đoạn ngắn hơn gần như luôn thành công ngay lần đầu). Sửa bằng cách giảm kích thước đoạn gộp
  (`_MAX_TTS_SEGMENTS` 8 → 16, mỗi đoạn ngắn hơn, đổi lại nhiều lượt gọi mạng hơn một chút) — Chương 8
  (VI) cuối cùng render thành công ở project 133, render job 197, QA PASS.
- **Gợi ý rút ra cho tương lai**: nếu một project cụ thể liên tục fail ở bước TTS trong khi test đoạn
  văn bản ngắn tương tự luôn thành công, nghi ngờ **đúng đoạn gộp cụ thể** (không phải môi trường/máy)
  trước — tái tạo lại chính xác đoạn văn bản thật (không phải đoạn tự viết tay để test) và thử lặp lại
  nhiều lần trên đúng đoạn đó trước khi đổi hướng điều tra.
