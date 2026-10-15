# STRATEGY — reverse-engineer kênh tham khảo & kế hoạch series "sinh tồn khắc nghiệt"

> **Mục 8.2 (preset Remotion cần build) đã bị thay thế một phần bởi [`TEMPLATE.md`](TEMPLATE.md)
> (2026-10-15)**: `TacticalMap`, `ambient` (rain/snow/wind/embers) và SFX tổng hợp đã có sẵn trong
> Documentary (feature 188) — đọc `TEMPLATE.md` trước khi quyết định có cần build thêm
> `MechanismCutaway`/`HubDiagram` không. Phần còn lại của tài liệu này (phân tích kênh, công thức kịch bản,
> danh sách chủ đề, style guide §7) vẫn đúng, không đổi.

> Dựa trên [`CHANNEL.md`](CHANNEL.md) (phân tích 3 video thật: transcript đầy đủ qua faster-whisper, đếm từ
> thật, xem 39 khung hình thật) + audit trực tiếp mã nguồn repo này (không suy đoán tính năng). Nhãn
> **FACT** (có bằng chứng trực tiếp) / **INFERENCE** (suy luận hợp lý từ FACT) / **HYPOTHESIS** (cần kiểm
> chứng) / **UNKNOWN** (chưa đủ dữ liệu) được giữ xuyên tài liệu — đọc nhãn trước khi hành động theo mục đó.

---

## 1. Executive summary

- Đã xem đúng **3/6+ video** của kênh tham khảo. Công thức kịch bản (10 beat, xem mục 5) lặp lại nhất quán ở
  cả 3 — **FACT**. Nhưng chỉ 1/3 video có view cao được ghi nhận (458K, video Nhật); 2 video còn lại không có
  số liệu view trong tài liệu gốc. **Không thể kết luận công thức kịch bản là nguyên nhân gây view cao** —
  đây là **UNKNOWN**, không phải điểm yếu của phân tích mà là giới hạn thật của dữ liệu đang có.
- Pipeline hiện tại (`backend/app/modules/documentary` + Remotion `remotion/src`) đã có **kiến trúc render
  tái dùng được thật sự**: schema `Scene`/`SceneText`, timing theo `cueFrame`, các primitive animation
  (`Appear`, `useEnter`, `Highlight`), 2 preset đã gần giống nhu cầu (`TimelineBuild`, `SplitComparison`) —
  **FACT**, đã đọc trực tiếp `remotion/src/presets.tsx`. Nhưng **ngôn ngữ hình ảnh hoàn toàn khác**: hệ
  thống hiện tại vẽ theo phong cách "giấy cũ/archival" (`PaperBackground`, `Halftone`, font serif), kênh
  tham khảo dùng flat-vector màu phẳng viền đen — **FACT**, cần preset mới chứ không sửa preset cũ.
- TTS (`edge_tts`, miễn phí), caption (`caption/segmentation.py`), QC (`quality/analyzer.py`,
  `postqa/analyzer.py`) là các module **ngôn ngữ-nội dung trung lập**, tái dùng gần như nguyên vẹn —
  **FACT**. `scene_director/classifier.py` hiện được viết riêng cho cảnh kịch tính hư cấu (chấm điểm theo
  động từ bạo lực, cường độ cảm xúc, số nhân vật) — **không áp dụng được** cho cảnh diagram khoa học, cần
  logic phân loại cảnh mới hoặc gán preset thủ công cho pilot đầu tiên.
- Khuyến nghị mặc định: **giữ khung kịch bản 10 beat làm baseline, không bịa chủ đề mới chưa kiểm chứng
  được khoa học thật, build 2-3 preset Remotion mới (không viết lại hệ thống) cho diagram/hub đa chức năng,
  và chạy pilot 1 video 45-60s trước khi làm video đầy đủ.** Lý do chọn phương án này thay vì các phương án
  khác được nêu ở từng mục tương ứng bên dưới.

---

## 2. Những điểm nên giữ nguyên từ kênh tham khảo

| Yếu tố | Bằng chứng | Nhãn | Khuyến nghị |
|---|---|---|---|
| Hook mở bằng 1 cảnh cụ thể + câu hỏi nghịch lý trong 30-50s đầu | Cả 3 video đều mở bằng cảnh người/gia đình cụ thể + câu hỏi "sao làm vậy/sao sống sót" (xem transcript 3 video) | FACT (cấu trúc) / HYPOTHESIS (hiệu quả giữ chân) | Giữ nguyên nguyên lý — đây là kỹ thuật hook phổ quát của thể loại explainer, không riêng của kênh này |
| 1 nguyên lý khoa học/vật lý thật làm trung tâm, không phải danh sách sự kiện rời rạc | 3/3 video đều có 1 nguyên lý rõ (sưởi người không sưởi phòng; thermal mass; 2 kẻ thù vô hình) | FACT | Giữ nguyên — đây là lý do nội dung "có phát hiện" chứ không phải liệt kê trivia |
| "The next time you..." — outro callback hình ảnh mở đầu + liên hệ đời sống khán giả | Xuất hiện gần như nguyên văn ở cả 3 video (xem CHANNEL.md mục 5, beat 9) | FACT | Giữ nguyên **cấu trúc** (callback + liên hệ cá nhân), **không copy câu chữ** — viết lại bằng từ ngữ riêng |
| Hub đa chức năng (1 vật làm nhiều việc, gần như không lãng phí) | irori (Nhật), pech (Nga: Bake/Cook/Hot Water/Produce Biochar), khăn che mặt (Sa mạc: 5 jobs) — 3/3 | FACT | Giữ nguyên — đây là thiết bị kể chuyện mạnh để chốt "sự thông minh", không riêng gì về nhiệt độ |
| Nhịp đọc nhanh, đặc, ~180 từ/phút | Đếm từ thật: 179.8 / 178.3 / 180.5 wpm — rất nhất quán | FACT | Giữ làm chuẩn ước lượng độ dài kịch bản, **không phải** "chậm rãi" như cảm nhận ban đầu |

## 3. Những điểm nên tối ưu (cơ hội làm tốt hơn, có lý do cụ thể)

| Yếu tố | Vấn đề ở bản gốc | Đề xuất tối ưu | Chi phí/độ phức tạp |
|---|---|---|---|
| Đoạn thừa nhận mặt trái/giới hạn thật | Chỉ 1/3 video có (Nhật); Nga và Sa mạc tông tích cực tuyệt đối, dễ trôi vào "tô hồng" nếu người xem có kiến thức nền | **Chủ động thêm 1 câu thừa nhận giới hạn thật khi chủ đề có** (không bịa nếu không có) — tăng độ tin cậy mà không phá nhịp | Thấp — chỉ là kỷ luật viết kịch bản |
| Nguồn/độ chính xác khoa học | Không có cách nào xác minh kênh gốc có kiểm tra nguồn hay không — **UNKNOWN** | Hệ thống hiện tại đã có khung "claim + nguồn + disputed/note" (xem `vox_documentary_template/RULES.md`, module `documentary/research.py`) — áp dụng khung đó cho series mới là lợi thế có sẵn, không phải xây mới | Thấp — tái dùng pattern đã có, không phải code mới |
| Nhãn chữ trong hình (label, số liệu, tên) | Kênh gốc vẽ chữ **vào trong ảnh AI** (quan sát trực tiếp ở nhiều khung hình, vd nhãn "Bake/Cook/Hot Water/Produce Biochar") — rủi ro chữ bị méo/sai chính tả khi AI-gen, đã thấy vài nhãn hình dạng lạ (không chắc là lỗi, ghi nhận là **quan sát**, không khẳng định là lỗi) | Vẽ nhãn/số liệu bằng **code (SVG/React text)** thay vì để AI vẽ chữ vào ảnh — chữ luôn đúng 100%, đổi ngôn ngữ tức thời, không tốn thêm 1 lần gen ảnh | Trung bình — cần tách "hình nền" (AI hoặc vector) khỏi "lớp chữ" (code), xem mục 7-8 |
| Hệ số hội tụ văn hoá (convergent evolution) | Chỉ 1/3 video dùng (Sa mạc) dù là thiết bị tăng tin cậy rất mạnh | Chủ động tìm góc hội tụ văn hoá cho các chủ đề phù hợp (không ép nếu tư liệu không đủ) | Thấp — chỉ là tiêu chí chọn chủ đề, xem mục 6 |
| Nhận diện hình ảnh riêng | Phong cách flat-vector của kênh gốc không độc quyền (nhiều kênh explainer dùng chung ngôn ngữ này) | Dùng bảng màu + quy tắc nét riêng (mục 7) để không bị nhầm là bản sao, đồng thời tận dụng hạ tầng Remotion sẵn có | Trung bình |

## 4. Những giả thuyết cần kiểm chứng (chưa có đủ bằng chứng để quyết định)

1. **HYPOTHESIS:** công thức 10-beat này giữ chân người xem tốt hơn cấu trúc khác — chỉ xác nhận được bằng
   retention thật sau khi đăng, tài liệu hiện tại không có dữ liệu analytics.
2. **HYPOTHESIS:** nhịp 180 từ/phút phù hợp với audience mục tiêu của series mới (có thể khác audience gốc
   nếu đổi ngôn ngữ sang tiếng Việt — tốc độ đọc tự nhiên/dễ nghe của tiếng Việt khác tiếng Anh).
3. **HYPOTHESIS:** thesis "1 nguyên lý khoa học trung tâm" dễ tìm với mọi chủ đề — một số chủ đề liền kề
   (mục 6, nhóm D) có thể KHÔNG có 1 nguyên lý gọn như vậy, cần research trước khi cam kết sản xuất.
4. **UNKNOWN:** vì sao video Nhật có 458K view còn các video khác (theo ảnh thumbnail ban đầu) có view thấp
   hơn nhiều (5.7K-19K) dù cùng công thức, cùng kênh. Có thể do: chủ đề (Nhật Bản phổ biến hơn), thời điểm
   đăng, thuật toán đề xuất, hoặc hoàn toàn ngẫu nhiên. **Không dùng con số 458K để dự đoán hiệu quả series
   mới** — đây là lỗi suy luận "từ 1 mẫu thành công suy ra công thức chung" mà brief đã cảnh báo tránh.
5. **HYPOTHESIS:** preset Remotion mới (mục 7-8) đủ linh hoạt để diễn tả mọi loại cơ chế khoa học khác nhau
   (nhiệt, nước, áp suất, sinh học) — chỉ xác nhận được sau khi thử xây 2-3 preset thật cho pilot.

---

## 5. Công thức kịch bản đề xuất

### 5.1 Beat nào là cốt lõi — giữ ở mọi tập

| Beat | Vai trò | Vì sao cốt lõi |
|---|---|---|
| Hook cảnh cụ thể + câu hỏi | Giữ người xem ở 10s đầu | Không có hook cụ thể = mất người xem trước khi vào nội dung |
| Lật giả định / kẻ thù thật | Tạo giá trị "tôi tưởng khác" | Đây là nguồn gốc của "nghịch lý" trong tiêu đề — bỏ beat này thì tiêu đề thành trivia phẳng |
| Nguyên lý khoa học trung tâm, có ví dụ cụ thể | Giá trị kiến thức cốt lõi | Không có = chỉ còn kể chuyện, mất định vị "explainer có chiều sâu" |
| Hub đa chức năng / tổng hợp | Chốt "sự thông minh" thành hình ảnh nhớ được | Thiết bị kể chuyện mạnh nhất để biến thông tin rời rạc thành 1 ấn tượng |
| Outro callback + câu chốt | Để lại dư âm, tăng khả năng chia sẻ | Không có = video "hết" đột ngột, không đọng |

### 5.2 Beat có thể rút gọn hoặc bỏ tuỳ chủ đề

- **Đoạn thừa nhận mặt trái**: chỉ thêm khi có thật (mục 3) — không viết "giả tạo khiêm tốn".
- **"So let's step back..."**: giữ *chức năng* (đoạn chuyển sang tổng kết) nhưng viết câu chuyển riêng mỗi
  tập, không lặp cùng 1 cụm — tránh cảm giác công thức hoá khi xem nhiều tập liên tiếp (xem 5.3).
- **Hội tụ văn hoá độc lập**: chỉ dùng khi tư liệu thật đủ mạnh (≥2 nền văn hoá không liên hệ, có nguồn),
  không ép vào chủ đề chỉ có 1 nền văn hoá.

### 5.3 Nguy cơ nhàm chán nếu lặp lại — và cách tránh

Rủi ro lớn nhất của 1 công thức 10-beat cố định là xem 3-4 tập liên tiếp sẽ thấy "giống nhau". Dữ liệu 3
video cho thấy **chính kênh gốc cũng tránh điều này một phần**: downside-beat chỉ 1/3, "step back" chỉ
2/3 dùng cụm gần giống, hội tụ văn hoá chỉ 1/3. Tức là họ **không máy móc hoá 100% beat**, chỉ giữ khung,
đổi beat phụ theo chủ đề. Đề xuất áp dụng nguyên tắc tương tự, cộng thêm:

- **Mỗi tập phải có 1 "phát hiện riêng"** không chỉ đổi bối cảnh: ví dụ Nhật là "nghịch đảo tư duy sưởi ấm",
  Nga là "nguyên lý vật lý cụ thể (thermal mass)", Sa mạc là "2 kẻ thù vô hình". Khi chọn chủ đề mới (mục 6),
  bắt buộc trả lời được câu "nguyên lý ở đây khác gì nguyên lý các tập trước?" trước khi viết kịch bản.
- **Đổi vị trí beat "lật giả định"**: không phải lúc nào cũng đặt ngay sau hook — đôi khi lật giả định ngay
  trong câu hook (như video Sa mạc) thay vì tách riêng, tạo nhịp khác nhau giữa các tập.
- **Cân bằng lịch sử/khoa học/bình luận**: dữ liệu 3 video cho thấy tỉ lệ nghiêng về khoa học/cơ chế (phần
  lớn thời lượng), lịch sử/văn hoá làm khung mở-đóng, bình luận cá nhân gần như không có (kênh gốc giữ giọng
  trung lập/khách quan xuyên suốt — **FACT**, không thấy đoạn ý kiến chủ quan rõ rệt trong 3 transcript).
  Nếu series mới muốn có bản sắc riêng, **thêm 1 câu bình luận/liên hệ ngắn của người làm kênh ở outro**
  (theo đúng nguyên tắc "bình luận gốc" đã áp dụng cho `literature_vi` trong repo này) là điểm khác biệt rẻ,
  không phá cấu trúc.

### 5.4 Template kịch bản chuẩn đề xuất

```
1. HOOK (0:00-0:30, ~90 từ)       cảnh cụ thể + câu hỏi nghịch lý
2. LỜI HỨA (0:30-0:45, ~45 từ)    "đây là câu chuyện về..." — không bắt buộc dùng y nguyên cụm này
3. LẬT GIẢ ĐỊNH (0:45-2:00)       kẻ thù/vấn đề thật khác điều khán giả tưởng
4. NGUYÊN LÝ TRUNG TÂM (2:00-3:30)  1 nguyên lý khoa học, có ví dụ đời thường cụ thể
5. GIẢI PHÁP CON #1..#3 (3:30-6:30) mỗi khối: cơ chế → vì sao thông minh → [mặt trái nếu có thật]
6. HUB ĐA CHỨC NĂNG (6:30-7:30)   tổng hợp thành 1 hình ảnh/vật nhớ được
7. [HỘI TỤ VĂN HOÁ nếu có] (7:30-7:50)
8. CHUYỂN SANG TỔNG KẾT (7:50-8:10) câu chuyển riêng mỗi tập
9. RECAP (8:10-8:40)
10. OUTRO CALLBACK + BÌNH LUẬN RIÊNG + CÂU CHỐT (8:40-9:00)
```
~1.500-1.600 từ cho video 8-9 phút ở nhịp 180 từ/phút (khớp mục tiêu pilot 8-9 phút ở Nhiệm vụ F).

---

## 6. Chiến lược ý tưởng & 10 chủ đề đầu tiên

### 6.1 Hệ thống chấm điểm ý tưởng

7 tiêu chí, thang 1-5 (5 = mạnh nhất), **chỉ dùng để xếp thứ tự thử nghiệm sản xuất trước/sau, không phải
dự đoán view** (đúng nguyên tắc ở mục 4.4):

| Tiêu chí | Câu hỏi khi chấm |
|---|---|
| Sức hút câu hỏi | Người lạ đọc tiêu đề có dừng lại không, không cần biết trước bối cảnh? |
| Mức độ nghịch lý | Câu trả lời có thật sự ngược với trực giác số đông không? |
| Độ tin cậy/phong phú tư liệu | Có nguồn kiểm chứng được (sách, bài báo khoa học, không chỉ truyền miệng)? |
| Khả năng giải thích bằng hình ảnh | Cơ chế có vẽ được bằng diagram/mũi tên/so sánh, hay chỉ kể được bằng lời? |
| Độ khác biệt so với video đã có | Nguyên lý trung tâm có trùng tập trước không (xem 5.3)? |
| Khả năng tạo câu chuyện hoàn chỉnh | Có đủ chất liệu cho cấu trúc 10-beat (mục 5.4), không bị đuối giữa chừng? |
| Chi phí/độ phức tạp sản xuất | Cần bao nhiêu nghiên cứu/loại ảnh mới so với preset đã có? |

### 6.2 Phân nhóm nguồn ý tưởng

**Nhóm A — Cùng chủ đề, góc giải thích khác** (khai thác lại các mảng kênh gốc đã động tới nhưng đổi góc):

1. **"Why Did Arctic Peoples Build Their Homes Out of Snow?"**
   - Câu hỏi trung tâm: tuyết là thứ lạnh nhất xung quanh, sao lại dùng chính nó làm vật liệu giữ ấm?
   - Giả định bị lật: "tuyết = kẻ thù của hơi ấm" → tuyết nén chứa không khí, cách nhiệt tốt.
   - Nguyên lý cần nghiên cứu: cách nhiệt bằng không khí bị giữ trong vật liệu xốp (giống nguyên lý lông
     chim, bọt xốp) — **cần tìm nguồn vật lý thật về hệ số dẫn nhiệt của tuyết nén**, không bịa con số.
   - Nguồn cần tìm: tài liệu nhân học/kiến trúc bản địa Bắc Cực, không chỉ bài blog phổ thông.
   - Hình ảnh chủ đạo: cắt lớp igloo cho thấy lớp khí giữa băng; so sánh song song tuyết-xốp vs đá-đặc.
   - Rủi ro sai lệch: dễ lẫn lộn giữa các loại nhà băng khác nhau (igloo tạm thời đi săn vs nhà ở lâu dài) —
     cần làm rõ loại nào đang nói tới.
   - Ưu tiên: **cao** — cùng cấu trúc "vật liệu tưởng là kẻ thù hoá ra là giải pháp" như video Nhật (giấy),
     dễ tái dùng preset cắt lớp đã định làm cho pilot.

2. **"How Did People Survive Months Without Sunlight?"** (đêm vùng cực/Sámi)
   - Câu hỏi trung tâm: sống nhiều tháng không có ánh mặt trời ảnh hưởng gì, giải quyết thế nào?
   - Giả định bị lật: khán giả nghĩ "vấn đề chính là lạnh" → vấn đề thật có thể là nhịp sinh học/tâm lý.
   - Nguyên lý cần nghiên cứu: đồng hồ sinh học, thiếu vitamin D, chiến lược xã hội/ánh sáng nhân tạo truyền
     thống — **cần nguồn y học/nhân học thật**, đây là chủ đề dễ bịa nếu không cẩn thận.
   - Hình ảnh chủ đạo: đồ thị thời gian ánh sáng theo vĩ độ (dùng preset `TimelineBuild` có sẵn).
   - Rủi ro sai lệch: dễ lẫn giữa tác động sinh lý thật và truyền thuyết/văn hoá dân gian không kiểm chứng.
   - Ưu tiên: **trung bình** — khác hẳn trục "nhiệt độ" của kênh gốc, kiểm tra xem định vị có co giãn được không.

3. **"Why Are Desert Tents Black, Not White?"** (lều lông dê Bedouin)
   - Câu hỏi trung tâm: đen hấp thụ nắng nhiều hơn, sao không dùng màu sáng mát hơn?
   - Giả định bị lật: trực giác "màu sáng = mát hơn" đúng với da người nhưng sai với cấu trúc dệt thưa.
   - Nguyên lý cần nghiên cứu: dệt lông dê tự giãn nở khi ẩm (mưa) và co lại tạo khe thoát khí khi khô +
     hiệu ứng ống khói nhiệt — **cần nguồn vật lý dệt/kiến trúc du mục thật**, không suy diễn.
   - Hình ảnh chủ đạo: so sánh song song đen-dệt-thưa vs trắng-dệt-kín; sơ đồ luồng khí qua lớp dệt.
   - Rủi ro sai lệch: dễ đơn giản hoá quá mức thành "màu đen mát hơn" sai hoàn toàn nếu bỏ qua yếu tố dệt thưa.
   - Ưu tiên: **cao** — cùng khán giả quan tâm chủ đề sa mạc của kênh gốc, góc hoàn toàn mới (màu sắc, không
     phải che mặt).

**Nhóm B — Cùng nguyên lý, bối cảnh khác** (test xem nguyên lý có generalize được không):

4. **"Why Did North Africans Dig Their Homes Underground?"** (nhà hầm kiểu Matmata, Tunisia)
   - Nguyên lý: cùng "thermal mass" như bếp Nga nhưng dùng chính lòng đất, không tốn vật liệu/nhiên liệu.
   - Giả định bị lật: "sống dưới đất = tối tăm, ẩm thấp, tệ" → thực ra ổn định nhiệt quanh năm gần như miễn phí.
   - Nguồn cần tìm: kiến trúc học/nhân học Bắc Phi, tài liệu về nhiệt độ ổn định dưới lòng đất.
   - Hình ảnh chủ đạo: cắt lớp mặt đất cho thấy nhiệt độ ổn định theo độ sâu (biến thể của `TimelineBuild`
     dùng trục độ sâu thay vì thời gian).
   - Rủi ro: dễ nhầm với các kiểu nhà hầm khác (không phải tất cả vì lý do nhiệt — một số vì phòng thủ).
   - Ưu tiên: **cao** — tái dùng trực tiếp nguyên lý thermal mass đã nghiên cứu kỹ ở pilot (nếu pilot chọn
     Nga hoặc tương tự), giảm chi phí research.

5. **"Why Do Mongolian Herders Layer Felt Instead of Building Walls?"** (ger/yurt)
   - Nguyên lý: "sưởi người không sưởi không gian" trong bối cảnh du mục/di động — test thesis Nhật có
     generalize sang kiến trúc di động không.
   - Giả định bị lật: nhà kiên cố tưởng ấm hơn lều di động → lớp nỉ (felt) + bố trí trong ger làm được việc
     tương đương với chi phí/trọng lượng thấp hơn nhiều.
   - Nguồn cần tìm: nhân học du mục Trung Á, cấu trúc vật liệu nỉ.
   - Hình ảnh chủ đạo: cắt lớp ger cho thấy các lớp nỉ; so sánh trọng lượng/thời gian dựng vs nhà cố định.
   - Rủi ro: dễ lẫn giữa truyền thống Mông Cổ và các biến thể lều khác (yurt Trung Á có khác biệt vùng miền).
   - Ưu tiên: **trung bình-cao**.

**Nhóm C — Chủ đề liền kề phù hợp định vị** (mở rộng ra ngoài trục nhiệt độ, vẫn giữ "kỹ thuật dân gian đối
phó môi trường khắc nghiệt"):

6. **"How Did the Dutch Survive Living Below Sea Level?"**
   - Mối đe doạ khác hẳn: nước, không phải nhiệt độ — kiểm tra định vị series có co giãn ngoài "nóng/lạnh"
     được không.
   - Giả định bị lật: "sống dưới mực nước biển = chờ ngày bị nhấn chìm" → hệ thống đê/cối xay gió/polder là
     kỹ thuật chủ động, không phải may rủi.
   - Nguồn cần tìm: lịch sử kỹ thuật thuỷ lợi Hà Lan — chủ đề có tư liệu rất phong phú, rủi ro sai lệch thấp.
   - Hình ảnh chủ đạo: sơ đồ cắt lớp đê + cối xay gió bơm nước; timeline mở rộng polder qua các thế kỷ.
   - Ưu tiên: **cao** — tư liệu dồi dào, rủi ro sai lệch thấp, mở biên định vị có kiểm soát.

7. **"How Do People Live Permanently at the Top of the World?"** (thích nghi độ cao Andes/Tây Tạng)
   - Mối đe doạ khác: thiếu oxy, không phải nhiệt — kẻ thù vô hình tương tự cấu trúc video Sa mạc.
   - Giả định bị lật: khán giả nghĩ cơ thể người không thể thích nghi thật sự với độ cao → thích nghi sinh
     học thật (thể tích phổi, hemoglobin) + kỹ thuật canh tác/kiến trúc theo tầng độ cao.
   - Nguồn cần tìm: **sinh lý học độ cao có nguồn y khoa thật** — đây là chủ đề dễ lẫn khoa học thật với
     truyền thuyết, cần cẩn trọng đặc biệt.
   - Hình ảnh chủ đạo: so sánh song song cơ thể người vùng thấp vs vùng cao; hội tụ văn hoá (Andes vs Himalaya
     — 2 nơi không liên hệ cùng thích nghi, giống thiết bị video Sa mạc).
   - Ưu tiên: **cao** — có sẵn cấu trúc hội tụ văn hoá mạnh, nhưng cần research y khoa kỹ trước khi viết.

**Nhóm D — Chủ đề mới cần kiểm chứng trước khi đầu tư** (rủi ro cao hơn, nêu rõ lý do CHƯA nên sản xuất ngay):

8. **"How Did People Preserve Food for Months Without Refrigeration?"**
   - Rủi ro: đây là **nhiều kỹ thuật khác nhau** (lên men, sấy, muối, đông lạnh tự nhiên) tuỳ vùng, có thể
     KHÔNG rút gọn được thành 1 nguyên lý trung tâm gọn như các video gốc — cần research trước để xác định
     có tìm được 1 thesis thống nhất hay phải tách thành nhiều tập theo kỹ thuật.
   - Giả định có thể bị lật: "bảo quản = ngăn chặn phân huỷ" → thực ra nhiều kỹ thuật **chủ động dùng vi sinh
     vật có lợi để ngăn vi sinh vật có hại" (lên men) — nghịch lý "dùng sự phân huỷ để chống phân huỷ".
   - Lý do chưa nên sản xuất ngay: cần 1 vòng research riêng để kiểm tra giả thuyết thesis ở trên có đứng
     vững với tư liệu thật không, trước khi viết kịch bản.

9. **"How Did Polynesian Navigators Cross the Ocean Without Instruments?"**
   - Rủi ro: đây nghiêng về **kỹ năng/tri thức** hơn là "vật/kỹ thuật đối phó môi trường khắc nghiệt" — có
     thể lệch định vị series (mục 2 của CHANNEL.md xác định niche là về giải pháp vật chất/kiến trúc/sinh lý,
     không phải kỹ năng điều hướng). Cần quyết định rõ định vị series có bao gồm "tri thức sinh tồn phi vật
     chất" hay không trước khi đầu tư.
   - Lý do chưa nên sản xuất ngay: rủi ro định vị, không phải rủi ro tư liệu (tư liệu về điều hướng sao/sóng
     biển Polynesia khá phong phú và đáng tin).

### 6.3 Lưu ý chung cho cả 9 ý tưởng trên

Không có ý tưởng nào được khẳng định sẽ đạt view cao — bảng chấm điểm ở 6.1 chỉ nên dùng để **xếp thứ tự thử
nghiệm**, không phải cam kết kết quả. Tổng cộng mới đề xuất 9 ý tưởng cụ thể (không ép đủ 10 để tránh thêm 1
ý tưởng yếu chỉ cho đủ số — ý tưởng #10 nên để trống, bổ sung sau khi pilot cho thấy hướng nào ăn khách hơn).

---

## 7. Visual style guide (độc lập, không copy 1:1 kênh gốc)

**Nguyên tắc chủ đạo:** ưu tiên code (SVG/React trong Remotion, đã có sẵn hạ tầng — xem mục 8) cho mọi phần
có thể vẽ bằng hình học + chữ. Chỉ dùng ảnh AI cho phần cần tính hoạ hình tự do (nhân vật, bối cảnh văn hoá)
mà code không vẽ được hợp lý.

| Hạng mục | Quy tắc đề xuất | Vì sao |
|---|---|---|
| **Bảng màu** | 1 bảng màu nền (2-3 tông theo bối cảnh: lạnh/nóng/trung tính) + **1 bộ màu mã hoá dữ liệu cố định xuyên series**: đỏ-cam = nhiệt/nguy hiểm, xanh dương = lạnh/nước, vàng = năng lượng/ánh sáng, xám = vật liệu trung tính. Không đổi nghĩa màu giữa các tập. | Khán giả học được "ngôn ngữ màu" của kênh sau vài tập → hiểu diagram nhanh hơn không cần đọc chữ |
| **Tương phản** | Nền luôn đủ sáng để chữ đen đọc được (kiểm tra tỉ lệ tương phản ≥ 4.5:1 theo chuẩn WCAG AA cho văn bản) | Captions + nhãn chữ phải đọc được trên mobile |
| **Nét vẽ** | Viền đen dày cố định 1 độ dày (vd 4-6px ở khung 1920px) cho mọi shape vector; không trộn nhiều độ dày nét trong cùng 1 cảnh | Giữ cảm giác "vẽ tay nhất quán" dù nhiều cảnh do nhiều lần gen AI khác nhau tạo ra |
| **Thiết kế nhân vật** | 1 bộ quy tắc tỉ lệ cố định (đầu tròn/tỉ lệ đầu-thân, mắt chấm hoặc mắt tròn viền đen, không vẽ mũi) dùng làm **style prompt cố định** cho mọi lần gen nhân vật mới — không phải 1 bộ asset tái dùng y hệt (xem CHANNEL.md mục 4: kênh gốc cũng làm vậy, không phải asset cố định) | Nhất quán cảm giác mà vẫn linh hoạt theo bối cảnh văn hoá từng tập |
| **Trình bày diagram** | 4 loại chuẩn hoá thành component code riêng (xem mục 8.2): cắt lớp cơ chế, hub đa chức năng có nhãn, so sánh song song, timeline/đồ thị | Tái dùng được giữa các tập, test 1 lần dùng mãi |
| **Phân biệt cảnh kể chuyện vs cảnh giải thích** | Cảnh kể chuyện: ảnh toàn cảnh có bối cảnh/con người, không có nhãn chữ nổi. Cảnh giải thích: nền đơn giản hơn (trắng hoặc 1 màu phẳng), có nhãn chữ + mũi tên code. Không trộn 2 loại trong cùng 1 khung hình | Giúp não khán giả tự động chuyển "chế độ xem" (kể chuyện → học) không cần nói ra |
| **Chuyển động** | Reveal theo `cueFrame` khớp với từ khoá trong lời đọc (mũi tên/nhãn xuất hiện đúng lúc được nhắc tới), không chuyển động trang trí vô nghĩa. Pan/zoom nhẹ (Ken Burns) chỉ cho ảnh nền tĩnh, không dùng cho diagram có nhãn chữ (chữ di chuyển gây khó đọc) | Giữ nhịp 180 từ/phút không bị animation làm chậm lại hoặc rối mắt |
| **Nhãn chữ/typography** | 1 font sans-serif bold cho nhãn/diagram, 1 font khác (serif hoặc display) chỉ cho tiêu đề cảnh nếu cần — **nhãn luôn vẽ bằng code, không bao giờ để AI vẽ chữ vào ảnh** (xem mục 3) | Loại bỏ hoàn toàn rủi ro chữ sai chính tả/méo do AI image gen |
| **Nhất quán giữa ảnh AI gen riêng lẻ** | Cố định 1 style-prompt block dùng lại y nguyên cho mọi lần gen (giống cách `IMAGE_STYLE.md` của `vox_documentary_template` đã làm cho phong cách Baroque) + seed/reference image nếu provider hỗ trợ | Pattern đã có sẵn trong repo, chỉ cần viết lại style-prompt cho phong cách flat-vector thay vì Baroque |
| **Giảm lỗi khoa học trong ảnh AI** | Diagram mô tả cơ chế (hướng mũi tên, số liệu) **không bao giờ để AI tự vẽ** — chỉ AI vẽ phần hoạ hình (người, cảnh), còn mũi tên/số liệu/nhãn do code vẽ chồng lên dựa trên dữ liệu đã kiểm chứng (từ `claims`/`sources` có sẵn trong khung `documentary/research.py`) | Tách "nội dung khoa học phải đúng" khỏi "hoạ hình được phép sáng tạo" — đúng tinh thần cổng duyệt đã có trong `vox_documentary_template` |

---

## 8. Pipeline sản xuất đề xuất (đã audit code, không suy đoán)

> Đã đọc trực tiếp: `backend/app/modules/{documentary,scene_director,voice,caption,quality,postqa,motion,
> video_composer,thumbnail,ai}` và `remotion/src/{presets.tsx,schema.ts,collage.tsx,theme.ts}`. Phần nào
> chưa đọc source thật được ghi rõ là UNKNOWN, không giả định.

### 8.1 Tái dùng gần như nguyên vẹn (FACT)

| Module | Vai trò | Vì sao tái dùng được |
|---|---|---|
| `voice/providers.py` (`EdgeTTSProvider`) | TTS miễn phí, hỗ trợ nhiều ngôn ngữ | Trung lập nội dung — chỉ cần text + voice_id |
| `caption/segmentation.py`, `caption/ass_writer.py` | Chia caption theo từ/giây, xuất .ass | Trung lập nội dung, hoạt động trên text + timing bất kỳ |
| `quality/analyzer.py` (pacing, audio, caption) | Chấm điểm nhịp độ/âm thanh/caption trước khi duyệt | Logic không phụ thuộc thể loại nội dung |
| `postqa/analyzer.py` | Checklist QC cuối (gói hoàn chỉnh, âm lượng, thumbnail tồn tại, metadata) | Thuần kỹ thuật, áp dụng mọi video |
| `ai/cost_estimator.py` | Ước tính chi phí LLM/TTS/ảnh trước khi chạy, **từ chối bịa giá $0** khi chưa có bảng giá xác nhận | Đúng tinh thần "không bịa chi phí API" — nên dùng công cụ này thay vì tôi tự đoán giá |
| `documentary/research.py` + khung `claims/sources/disputed` | Quản lý nguồn, trích dẫn, đánh dấu tranh cãi | Đúng nhu cầu "không bịa cơ chế khoa học" của series mới |

### 8.2 Cần mở rộng (có nền, chưa đủ cho nhu cầu mới)

| Module | Hiện có | Cần thêm | Độ phức tạp |
|---|---|---|---|
| `remotion/src/presets.tsx` | 9 preset phong cách "giấy cũ/archival"; 2 preset (`TimelineBuild`, `SplitComparison`) gần đúng cấu trúc cần nhưng sai ngôn ngữ hình | Thêm **2 preset mới** tái dùng schema `Scene`/`SceneText` + primitive `Appear`/`useEnter` đã có: `MechanismCutaway` (cắt lớp cơ chế, mũi tên theo `cueFrame`) và `HubDiagram` (1 vật trung tâm nối nhiều nhãn chữ bằng đường code-vẽ) | Trung bình — tái dùng ~70% hạ tầng (schema, timing, animation helper), chỉ viết phần hình học/màu mới |
| `remotion/src/theme.ts`, `collage.tsx` | Định nghĩa `COLORS`/`FONTS` cho phong cách giấy cũ | Thêm 1 theme flat-vector mới (bảng màu mục 7) song song, không sửa theme cũ (các template khác còn dùng) | Thấp |
| `scene_director/classifier.py` | Chấm điểm cảnh **kịch tính hư cấu** (động từ bạo lực, cảm xúc, nhân vật) — đọc trực tiếp source, xác nhận không có khái niệm "cảnh diagram" | Viết 1 bộ phân loại khác (hoặc gán thủ công cho pilot): cảnh nào là "kể chuyện" (dùng preset ảnh/motion cũ) vs "giải thích" (dùng preset diagram mới) — **không sửa classifier cũ** vì các template khác (horror, zombie_system...) đang phụ thuộc nó | Trung bình, nhưng **cho pilot đầu tiên nên gán thủ công**, chưa cần tự động hoá (xem P0 vs P1 ở mục 10) |
| `thumbnail/scoring.py` | Chọn khung hình đẹp nhất **từ video AI đã render** (frame scoring) — không áp dụng được vì series mới không có AI-video clip để chọn khung | Thumbnail cho series mới nên **soạn như 1 cảnh Remotion riêng** (nhiệt kế/số liệu + nhãn code-vẽ) thay vì chọn từ frame — tận dụng đúng nguyên tắc "chữ do code vẽ" ở mục 7 | Thấp-trung bình |

### 8.3 Thực sự cần bổ sung mới (chưa có gì tương tự trong repo)

- **Scene-type cho nội dung diagram khoa học**: hiện `documentary` module có preset nhưng không có khái
  niệm tường minh "đây là cảnh diagram cần N nhãn + M mũi tên theo thứ tự xuất hiện khớp lời đọc" — cần mở
  rộng `ScriptSection`/`PlannedScene` (đã đọc `storyboard.py`) để mang theo metadata này, hoặc đơn giản hơn
  cho pilot: điền thủ công `scene.texts` với `cueFrame` tương ứng (không cần sửa schema ngay — xem 8.4).

### 8.4 Cách mô hình hoá scene types cho series này (đề xuất, chưa code)

Dùng lại đúng pattern đã có (`DocumentaryScene` + `visual_preset` + `texts[]` với `role`/`cueFrame`), chỉ
thêm 2 giá trị `visual_preset` mới (`MechanismCutaway`, `HubDiagram`) vào `storyboard.PRESETS` và
`render_plan.PRESET_COMPONENTS` tương ứng bên Remotion. Không cần đổi database schema vì `visual_preset` đã
là field tự do (đọc `storyboard.py` dòng 33-38: `PRESETS` là 1 tuple hằng số, thêm phần tử mới là đủ).

### 8.5 Cách chuyển từ script sang storyboard

Tái dùng nguyên `storyboard.plan_units()` (chia đoạn theo câu/từ, không theo giây cố định — đã đọc source).
Khác biệt duy nhất: người biên tập (không phải AI tự động, ít nhất ở pilot) **gán thủ công** preset nào cho
từng scene (`PhotoKenBurns` cho cảnh kể chuyện, `MechanismCutaway`/`HubDiagram`/`SplitComparison`/
`TimelineBuild` cho cảnh giải thích) — vì `scene_director` tự động hiện không hiểu khái niệm "cảnh diagram".

### 8.6 Quản lý asset và prompt

Tái dùng pattern `IMAGE_STYLE.md` (đã đọc cấu trúc `vox_documentary_template/`) — viết 1 file tương tự cho
style flat-vector (xem mục 7), cố định style-prompt block, không đổi giữa các lần gen trong cùng 1 tập.

### 8.7 Đồng bộ voice-over, caption, hình ảnh

Tái dùng cơ chế `cueFrame` đã có trong Remotion (texts xuất hiện đúng lúc trong khung hình) + pipeline
caption/timing hiện có (`voice/timing.py`, chưa đọc chi tiết — **UNKNOWN** mức độ tự động khớp từ khoá, cần
xác nhận trước khi cam kết tự động hoá hoàn toàn; pilot có thể căn tay nếu tool tự động chưa đủ chính xác).

### 8.8 Kiểm tra lỗi trước khi render cuối

Tái dùng `quality/analyzer.py` + `postqa/analyzer.py` nguyên vẹn (8.1). Thêm 1 bước thủ công bắt buộc cho
pilot: **người làm kênh tự đọc to kịch bản + tự soát từng nhãn chữ trên diagram khớp với nguyên lý khoa học
đã research** — không có check tự động nào thay được bước này ở giai đoạn pilot.

---

## 9. Kế hoạch sản xuất pilot

### 9.1 Quy trình 1 video pilot (8-9 phút, mục tiêu không bắt buộc)

| Bước | Việc làm | Công cụ |
|---|---|---|
| 1. Research brief | Chọn 1 chủ đề từ mục 6 (nhóm A/B/C, không chọn nhóm D cho pilot vì rủi ro cao hơn), liệt kê nguồn thật, xác định 1 nguyên lý trung tâm | Thủ công + `documentary/research.py` khung claims |
| 2. Viết kịch bản | Theo template 5.4, ~1.500-1.600 từ | Thủ công, đối chiếu claims |
| 3. Kiểm tra chính xác | Tự soát từng câu có dẫn chứng; đánh dấu `disputed` nếu số liệu gây tranh cãi | Khung `claims/sources` có sẵn |
| 4. Storyboard | `episode_builder.py storyboard` (đã có, dùng chung Vox pipeline) + gán thủ công preset mới cho cảnh diagram | `documentary/storyboard.py` |
| 5. Asset hình ảnh | Gen ảnh nền (nhân vật/bối cảnh) theo style-prompt cố định (8.6); nhãn/mũi tên để code vẽ, không gen | Tool gen ảnh hiện có + 2 preset Remotion mới |
| 6. Voice-over | `edge_tts`, miễn phí | `voice/providers.py` |
| 7. Dựng video | Remotion render, dùng preset mới cho cảnh diagram, preset cũ (`PhotoKenBurns`) cho cảnh kể chuyện | `documentary/render.py` |
| 8. QC | `quality/analyzer.py` + `postqa/analyzer.py` + tự nghe/xem toàn bộ | Có sẵn |
| 9. Thumbnail + metadata | Soạn như 1 cảnh Remotion riêng (8.2) + metadata theo `title_description_template.txt` có sẵn | Có sẵn mẫu |
| 10. Đánh giá sau đăng | Xem mục 9.3 | — |

### 9.2 Đoạn thử nghiệm 45-60 giây trước khi làm toàn bộ

Dựng **beat #1 (hook) + 1 cảnh diagram mẫu** trước — đây là đoạn kiểm tra rẻ nhất cho 2 rủi ro lớn nhất:
(a) 2 preset Remotion mới có vẽ ra đúng cảm giác flat-vector mong muốn không, (b) giọng đọc + nhịp 180
từ/phút có nghe tự nhiên không. Nếu đoạn 45-60s không đạt, sửa trước khi tốn công viết hết kịch bản 9 phút.

### 9.3 Ngân sách

Ngân sách thử nghiệm ~10 USD. Ưu tiên theo thứ tự: (1) edge_tts miễn phí cho voice, (2) chuyển động bằng
code (Remotion/FFmpeg) thay vì video AI tốn phí, (3) chỉ chi tiền cho ảnh AI ở phần hoạ hình thật sự cần.
**Không giả định giá bất kỳ API ảnh/video nào** — chạy `ai/cost_estimator.py` với số lượng cảnh/ảnh dự kiến
thật của pilot trước khi commit, vì module này đã có cơ chế từ chối bịa giá khi chưa xác nhận (đọc trực tiếp
`cost_estimator.py`, `pricing.py`).

---

## 9.4 Kế hoạch kiểm chứng 3 video

| | Chi tiết |
|---|---|
| **Biến cố định** | Cấu trúc 10-beat (mục 5.4), bảng màu/nét vẽ (mục 7), nhịp đọc mục tiêu ~180 từ/phút, quy trình QC (8.1/9.1) |
| **Biến thay đổi** | Chủ đề (chọn từ 3 nhóm khác nhau ở mục 6 để test độ co giãn định vị), có/không có đoạn thừa nhận mặt trái, có/không hội tụ văn hoá |
| **Chỉ số ghi nhận** | View, watch time/retention curve (nếu nền tảng cung cấp), CTR thumbnail, tỉ lệ xem hết — **ghi nhận thật, không đặt ngưỡng kỳ vọng trước** (đúng nguyên tắc không đặt ngưỡng CTR/retention tuỳ ý) |
| **Đánh giá hiệu quả nội dung** | So sánh retention curve giữa 3 video cùng cấu trúc nhưng khác chủ đề/biến phụ — tìm điểm rớt người xem trùng lặp giữa các video (nếu có, chỉ ra beat yếu thật, không phải beat bị nghi ngờ) |
| **Đánh giá hiệu quả sản xuất** | Thời gian/chi phí thật mỗi bước (9.1) so với ước tính — xác nhận preset mới có thực sự tiết kiệm công sức như kỳ vọng ở mục 8.2 không |
| **Kết luận CHƯA thể đưa ra sau 3 video** | Chưa đủ để: (a) khẳng định cấu trúc 10-beat là tối ưu, (b) khẳng định nhóm chủ đề nào "tốt hơn" nhóm khác, (c) khẳng định định vị series có nên mở rộng ngoài nhiệt độ/môi trường vật lý hay không — cần ít nhất 8-10 video và thời gian đủ để thuật toán nền tảng ổn định phân phối mới kết luận được xu hướng thật |

---

## 10. Danh sách công việc theo thứ tự ưu tiên

### P0 — bắt buộc trước khi sản xuất pilot

| # | Đầu ra | Lý do | Phụ thuộc | Cách xác nhận hoàn thành |
|---|---|---|---|---|
| 1 | Chọn 1 chủ đề pilot từ nhóm A/B/C (mục 6.2), viết research brief có nguồn thật | Không có chủ đề = không làm được gì tiếp | Không | Research brief có ≥1 nguyên lý trung tâm + nguồn kiểm chứng được, không có số liệu bịa |
| 2 | Viết style-prompt flat-vector cố định (theo mẫu `IMAGE_STYLE.md`) | Cần trước khi gen bất kỳ ảnh nào để đảm bảo nhất quán | Mục 7 | File style-prompt tồn tại, dùng được lại nguyên văn cho nhiều cảnh |
| 3 | Code 2 preset Remotion mới: `MechanismCutaway`, `HubDiagram` | Đây là phần "thực sự cần bổ sung" duy nhất để khớp ngôn ngữ hình ảnh mục tiêu | Audit 8.2 đã xong | Preset render ra 1 cảnh test đúng với mô tả mục 7, không lỗi runtime |
| 4 | Dựng đoạn test 45-60s (hook + 1 cảnh diagram) | Kiểm tra rẻ nhất 2 rủi ro lớn nhất trước khi đầu tư cả video (9.2) | #1, #2, #3 | Xem/nghe thử đoạn test, tự đánh giá đạt/không đạt bằng mắt/tai thật, không đoán |
| 5 | Chạy `ai/cost_estimator.py` với số liệu thật của pilot | Tránh vượt ngân sách 10 USD, tránh bịa giá | #1 | Có report cost_estimator thật, không phải số tự đoán |

### P1 — chỉ thực hiện sau khi pilot chứng minh được nhu cầu

| # | Đầu ra | Lý do | Phụ thuộc | Cách xác nhận hoàn thành |
|---|---|---|---|---|
| 1 | Sản xuất đủ 3 video theo kế hoạch mục 9.4 | Pilot 1 video không đủ để so sánh biến số | Pilot 1 đạt QC | 3 video đã đăng, có chỉ số ghi nhận thật |
| 2 | Viết logic phân loại cảnh "kể chuyện vs giải thích" tự động (thay gán tay ở 8.5) | Chỉ đáng làm khi đã xác nhận quy trình thủ công hoạt động và tốn thời gian thật đáng kể | ≥1 video pilot hoàn thành, có số liệu thời gian thật về việc gán tay tốn bao lâu | Logic mới chạy trên ≥3 tập, kết quả gán preset khớp đánh giá thủ công ≥ tỉ lệ do người quyết định khi bắt đầu |
| 3 | Thumbnail-as-Remotion-scene thay vì quy trình thủ công | Chỉ cần tự động hoá nếu làm nhiều tập (>3) | P1-1 | Thumbnail tạo ra từ 1 lệnh, không cần Photoshop/sửa tay |
| 4 | Mở rộng sang 2-3 chủ đề nhóm D sau khi research riêng xác nhận có nguyên lý trung tâm | Nhóm D rủi ro cao hơn, cần xác nhận trước (mục 6.2) | Research riêng từng chủ đề nhóm D | Research brief của chủ đề nhóm D đạt chuẩn như P0-1 |

### P2 — tối ưu dài hạn

| # | Đầu ra | Lý do | Phụ thuộc | Cách xác nhận hoàn thành |
|---|---|---|---|---|
| 1 | Mở rộng `storyboard`/`scene_director` để hiểu khái niệm "cảnh diagram" ở mức schema (8.3), không chỉ gán tay | Chỉ đáng đầu tư khi series chạy ổn định lâu dài | P1-2 chạy ổn | Schema mới không phá vỡ template khác đang dùng `scene_director` (horror, zombie_system...) |
| 2 | Bộ 4+ preset diagram đầy đủ (thêm biến thể ngoài 2 preset P0 ban đầu) | Đa dạng hoá hình ảnh khi làm nhiều tập, tránh nhàm (mục 5.3) | Đã có ≥5-6 tập thực tế để biết loại diagram nào còn thiếu | Preset mới dùng được cho ≥2 chủ đề khác nhau mà không sửa code riêng từng tập |
| 3 | Hệ thống chấm điểm ý tưởng (6.1) có dữ liệu thật thay vì thang điểm chủ quan ban đầu | Chỉ có dữ liệu thật sau khi đã đăng đủ nhiều video để so sánh | ≥8-10 video đã đăng | Thang điểm được hiệu chỉnh lại dựa trên tương quan thật giữa điểm dự đoán và kết quả thật (không giả định tương quan trước khi có dữ liệu) |
