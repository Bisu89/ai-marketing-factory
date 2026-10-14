# CHANNEL — phân tích kênh A (flat-vector explainer) & định hướng series "sinh tồn khắc nghiệt"

> **Phạm vi:** file này chỉ phân tích **kênh A** (3 video). Kênh B ("Before Civilization", 2 video) và bảng
> tổng hợp liên kênh nằm trong [`SYNTHESIS.md`](SYNTHESIS.md). Series mới là bản blend, không theo riêng kênh nào.

> **Trạng thái: bản nháp phân tích, chưa sản xuất tập nào.** Dựa trên **3 video tham khảo** tải thủ công
> vào `phantichvideo/` và phân tích trực tiếp (audio dịch thật bằng faster-whisper, xem khung hình thật,
> không đoán từ thumbnail). Kênh gốc có ít nhất 6 video; phần "công thức" dưới đây đã được xác nhận lặp lại
> giống nhau ở cả 3 mẫu nên độ tin cậy cao hơn bản nháp đầu, nhưng vẫn chưa phải toàn bộ kênh.

## 1. Nguồn phân tích

| Video | Thời lượng | Views (lúc xem) | File |
|---|---|---|---|
| "How Did Japanese People Survive Winter in Houses Made of Paper?" | 13:54 | ~458K/5 ngày | `...OQCl9rN0xyM...` |
| "Why Did Russians Sleep on Top of a Stove at −40°C?" | 14:24 | — | `...7YCxuYHSwn0...` |
| "Why Do Desert People Cover Their Faces?" | 11:10 | — | `...lP9z2TGxPT4...` |

Các video khác cùng kênh thấy qua thumbnail (chưa phân tích sâu): "How Did They Survive −71°C?",
"How Did Desert Mothers Keep Babies Alive in Extreme Heat?", "How Did Desert People Actually Sleep in 45°C Heat?",
"What Did Romans Actually Do All Day?".

**Phương pháp (áp dụng cho cả 3):** tải video thật → tách audio bằng ffmpeg → dịch toàn văn bằng faster-whisper
(local, model `small`) → đếm từ thật bằng `wc -w` (không ước lượng bằng mắt) → xem trực tiếp 11-14 khung hình
cách nhau 60s mỗi video để xác nhận phong cách hình.

**Sửa lại số liệu sai ở bản nháp đầu:** nhịp đọc ước lượng ban đầu "~100 từ/phút, chậm/chắc" từ việc xem lướt
1 video là **sai**. Đếm từ thật cho cả 3 video:

| Video | Số từ (đếm thật) | Thời lượng | Từ/phút |
|---|---|---|---|
| Nhật (nhà giấy) | 2.498 | 833.6s | **179.8** |
| Nga (ngủ trên bếp) | 2.568 | 864.1s | **178.3** |
| Sa mạc (che mặt) | 2.016 | 670.0s | **180.5** |

Nhịp đọc **~179-180 từ/phút, cực kỳ nhất quán giữa 3 video** — đây là nhịp khá nhanh/dày đặc thông tin cho thể
loại explainer, không phải chậm rãi như đánh giá cảm tính ban đầu. Viết kịch bản theo công thức này phải tính
~180 từ/phút khi ước lượng độ dài tập.

## 2. Định vị niche

- **Sứ mệnh:** giải thích "con người từng sống sót thế nào trong điều kiện khí hậu khắc nghiệt" — mỗi tập một
  câu hỏi "nghe vô lý" (nhà giấy giữa mùa đông, ngủ trên bếp lò ở -40°C, che kín mặt dù trời lặng gió), trả lời
  bằng cơ chế khoa học thật + đúc kết thành 1 nguyên lý phản trực giác.
- **Khán giả:** người xem giải trí-giáo dục nhẹ (kiểu Kurzgesagt/TED-Ed/Vox) — tò mò nhanh, không cần kiến thức nền.
- **Mỗi tập xoay quanh một nguyên lý khoa học trung tâm**, nêu ra sớm hoặc giữa tập rồi lặp lại dưới dạng khác:
  - Nhật: "sưởi con người, không sưởi căn phòng" (nguyên lý triết lý/thiết kế)
  - Nga: "thermal mass" — khối gạch lớn hấp thụ nhiệt nhanh, nhả chậm (nguyên lý vật lý cụ thể)
  - Sa mạc: che mặt chống **2 kẻ thù vô hình** (mất nước qua hơi thở + nhiệt bức xạ), gió/cát chỉ là lý do bề nổi
- **Sửa lại giả định sai ở bản nháp đầu:** "luôn có 1 câu thừa nhận mặt trái" **không đúng cho cả 3 video**.
  Chỉ video Nhật có đoạn thừa nhận rõ (khói irori hại phổi/mắt). Video Nga và Sa mạc **không có** đoạn thừa nhận
  mặt trái nào — cả hai giữ tông tích cực/thán phục xuyên suốt. Đừng ép buộc yếu tố này vào mọi tập.

## 3. Công thức tiêu đề & thumbnail

**Tiêu đề:** `[Nhóm người] + [sống sót/làm gì/vì sao] + [điều kiện khắc nghiệt, thường có số liệu]`
- "How Did Japanese People Survive Winter in Houses Made of Paper?"
- "Why Did Russians Sleep on Top of a Stove at −40°C?"
- "Why Do Desert People Cover Their Faces?" (video này không có số liệu độ — vẫn ăn công thức nhờ "Why...?" +
  hành vi nghe phản trực giác, nên **số liệu không bắt buộc**, chỉ là một biến thể mạnh)

Luôn kết thúc bằng dấu hỏi. Luôn đặt câu hỏi mà bản thân video sẽ lật ngược giả định của khán giả.

**Thumbnail:** nền minh họa flat-vector, vật chủ đạo gợi cảm giác khắc nghiệt (nhiệt kế, hoặc tình huống rõ),
chữ tiêu đề viết tay/bold màu vàng viền đen dày, nhân vật/cảnh đơn giản. Nhất quán giữa các video → nhận diện
kênh qua phong cách hình, không phải logo.

## 4. Phong cách hình ảnh (xem trực tiếp 39 khung hình tổng cộng qua 3 video, không đoán)

**Sửa lại giả định sai ở bản nháp đầu:** không phải "thư viện asset tái sử dụng y hệt" — mức độ chi tiết nhân
vật **khác nhau giữa các video** (gia đình kimono ở video Nhật đơn giản hơn bà lão có nếp nhăn chi tiết ở video
Nga; người du mục sa mạc lại có phong cách khác nữa). Đây giống một **"house style" được brief nhất quán** (nét
viền đen dày, màu phẳng, bố cục diagram) hơn là một bộ asset cố định dùng đi dùng lại — khả năng cao là ảnh vẽ
tay hoặc AI-gen riêng cho từng video theo cùng 1 style guide, không phải thư viện SVG tái chế.

**3 lớp cảnh tái diễn, nhất quán cả 3 video:**
1. **Cảnh bối cảnh lịch sử/văn hoá** — nhân vật đơn giản, tông màu theo bối cảnh (đất trầm mùa đông Nga/Nhật,
   vàng cháy cho sa mạc).
2. **Diagram khoa học nền trắng** — đây là phần dùng nhiều thiết bị hình ảnh lặp lại rõ nhất, xác nhận ở cả 3 video:
   - **Sơ đồ cắt lớp cơ chế** (airflow dưới sàn nhà Nhật; mê cung khói trong bếp Nga; cắt lớp khoang mũi lọc bụi sa mạc)
   - **Hub đa chức năng có nhãn chữ** (irori Nhật nối tới nồi/đèn/sấy quần áo; bếp Nga nối "Bake/Cook/Hot Water/
     Produce Biochar"; khăn che mặt sa mạc → "5 jobs, one garment") — mô-típ này lặp lại ở **cả 3/3 video**, là
     thiết bị hình ảnh đáng tin cậy nhất để mô tả nguyên lý "một vật làm nhiều việc, không lãng phí"
   - **So sánh cặp đôi song song** (gạch dày vs gỗ mỏng hấp thụ nhiệt; mặc kín-mát vs để lộ da-nóng; pechka gạch
     vs bếp sắt hiện đại)
   - **Timeline/đồ thị thời gian** (chu kỳ 4 mùa ngôi nhà Nhật; nhiệt độ ổn định 24h của khối gạch Nga; hành
     trình hang động→thành phố hiện đại sa mạc)
3. **Nhân vật "stickman" trắng tròn, nét que** — xuất hiện cả dạng full-scene (mở đầu video Sa mạc, đứng giữa
   sa mạc) lẫn dạng minh hoạ trong diagram (nằm trên bếp Nga hấp thụ nhiệt, demo "cách làm sai" 3 khung sa mạc).
   Đây chính là nhân vật trong thumbnail — vai trò: liên hệ hiện đại + minh hoạ thao tác + đôi khi hài.

Nét vẽ chung: viền đen dày, phẳng, không gradient phức tạp. Khác hẳn pipeline ảnh AI photoreal đang dùng cho
Vox Documentary Factory trong repo này — xem mục 6.1.

## 5. Khung kịch bản (xác nhận lặp lại ở cả 3 video — độ tin cậy cao hơn bản nháp đầu)

| # | Đoạn | Vai trò | Xác nhận ở |
|---|---|---|---|
| 1 | Hook cảnh cụ thể + câu hỏi nghịch lý | Mở bằng 1 khoảnh khắc cụ thể (gia đình ngủ trên bếp -40°C; người đi qua sa mạc lặng gió vẫn che mặt) + câu hỏi "sao làm vậy/sao sống sót" | 3/3 |
| 2 | "This is the story of..." | Câu hứa hẹn rõ ràng sẽ giải thích nguyên lý đằng sau | 3/3 |
| 3 | Lật giả định / kẻ thù thật | Vấn đề thật không phải cái khán giả nghĩ (Nhật: hè nóng ẩm mới là vấn đề thiết kế chính; Sa mạc: không phải gió/cát mà là mất nước+bức xạ) | 3/3 (rõ nhất ở Nhật & Sa mạc) |
| 4 | Nguyên lý khoa học trung tâm, có ví dụ/so sánh cụ thể | Giải thích 1 cơ chế vật lý dễ hiểu bằng ví dụ đời thường (nồi sắt mỏng vs gang dày = thermal mass) | 3/3 |
| 5 | Các khối giải pháp/cơ chế con | Mỗi khối: cách hoạt động → vì sao thông minh. **Không bắt buộc có câu thừa nhận mặt trái** (chỉ Nhật có) | 3/3, mặt trái chỉ 1/3 |
| 6 | Hub đa chức năng | Tổng hợp: 1 vật/giải pháp làm được nhiều việc cùng lúc, gần như không lãng phí gì | 3/3 |
| 7 | **"So let's step back..."** | Cụm chuyển cảnh gần như nguyên văn xuất hiện ở Nhật ("let's step back and take in the full picture") và Nga ("let's step back and appreciate what these people accomplished") — mở đoạn tổng kết trước outro | 2/3 rõ, Sa mạc dùng biến thể "let's put the whole picture together" |
| 8 | Recap dồn dập | Tóm tắt nhanh từng ý đã nói, không thêm thông tin mới | 3/3 |
| 9 | **"The next time you..."** | Công thức outro gần như cố định: callback hình ảnh mở đầu + hướng khán giả liên hệ đời sống hiện tại của chính họ ("next time you picture...", "next time you're cold and reach for your thermostat...", "next time you picture that figure in the desert...") | 3/3, rất đáng tin cậy — **đây là câu mở outro nên copy sát công thức nhất** |
| 10 | Câu chốt thơ hoá nguyên lý | 1 câu ngắn, dễ nhớ, lặp lại nguyên lý trung tâm bằng ngôn ngữ giàu hình ảnh | 3/3 |

**Thiết bị phụ đáng chú ý, không phải lúc nào cũng có:**
- **Hội tụ văn hoá độc lập** (chỉ thấy ở video Sa mạc): nêu nhiều nền văn hoá không liên hệ (Tuareg, Bedouin,
  dân du mục Trung Á) đều tự đi đến cùng giải pháp → dùng để tăng độ tin cậy "tự nhiên quy định quy luật, không
  phải trùng hợp". Thiết bị mạnh, dùng khi chủ đề có đủ tư liệu đối chiếu đa văn hoá thật.
- **Đoạn thừa nhận mặt trái/khó khăn thật** (chỉ thấy ở video Nhật — khói hại phổi): làm tăng tin cậy khi có,
  nhưng không bắt buộc.

**Quy tắc khi viết kịch bản theo công thức này:**
- Phải có 1 nguyên lý khoa học/vật lý **thật, kiểm chứng được** làm trung tâm — không bịa cơ chế.
- Ước lượng độ dài bằng ~180 từ/phút (không phải 100 như nháp đầu).
- Câu mở đoạn "this is the story of..." và câu outro "the next time you..." là 2 điểm neo công thức chắc nhất —
  nên viết sát theo cấu trúc này nhất trong toàn bộ khung.
- Không ép buộc đoạn "thừa nhận mặt trái" nếu chủ đề không có mặt trái thật đáng kể — tô hồng giả tạo tệ hơn bỏ qua.

## 6. Việc cần quyết định trước khi sản xuất tập đầu

1. **Pipeline hình ảnh chưa có trong hệ thống hiện tại.** Vox Documentary Factory dùng ảnh tư liệu + AI photoreal;
   manhua dùng ảnh nhân vật nhất quán kiểu truyện tranh. Phong cách flat-vector-doodle + diagram mũi tên của
   niche này là một hướng khác hẳn, và mục 4 cho thấy nó không phải 1 bộ asset cố định mà là 1 "house style"
   được brief lại mỗi video — nghĩa là **cần 1 style prompt/bộ quy tắc hình ổn định**, không chỉ 1 bộ ảnh tái dùng.
   Cần quyết định: thuê animator ngoài, dùng thư viện asset có sẵn (Storyblocks/Vyond-style), hay tìm model AI
   tạo được flat-vector nhất quán theo style guide. Chưa có câu trả lời, đừng giả định.
2. **Danh sách chủ đề/số** — cần kho câu hỏi dạng "[nhóm người] sống sót/làm gì trong [điều kiện khắc nghiệt]"
   đủ nhiều để lên lịch; mỗi chủ đề phải có đủ tư liệu thật để rút ra 1 nguyên lý khoa học/vật lý kiểm chứng
   được, không bịa cơ chế. Số liệu độ không bắt buộc (xem video Sa mạc) nhưng là biến thể mạnh.
3. Ngôn ngữ kênh: làm bản tiếng Anh gốc (như kênh tham khảo) hay chuyển ngữ Việt? Ảnh hưởng tới văn phong câu thesis.
4. Đã xem 3/6+ video của kênh gốc, công thức đã xác nhận lặp lại nhất quán ở cả 3 — độ tin cậy tốt để bắt đầu
   viết kịch bản mẫu thử, nhưng vẫn chưa xem video view thấp nhất (5.7K) để kiểm tra có lệch công thức không.
