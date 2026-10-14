# PILOT — "Why Did Some Inuit Hunters Build Shelters Out of Snow?" (45-60s test segment)

> Tiếp nối [`STRATEGY.md`](STRATEGY.md). Tài liệu này KHÔNG lặp lại phân tích kênh tham khảo hay đánh giá
> chiến lược — chỉ là kế hoạch triển khai cụ thể cho đoạn pilot 45-60 giây đầu tiên. Mọi chi tiết code dưới
> đây đã được **đọc trực tiếp từ source thật** trong phiên làm việc này (không phải suy đoán từ báo cáo
> trước) — xem mục 7 để biết chính xác file nào đã đọc và phát hiện gì khác với giả định trước.

---

## 1. Executive recommendation

- **Đổi tên chủ đề pilot** từ "Why Did Arctic Peoples Build Their Homes Out of Snow?" (tiêu đề gốc trong
  yêu cầu) thành **"Why Did Some Inuit Hunters Build Shelters Out of Snow?"** — lý do ở mục 2.1, dựa trên
  nghiên cứu thật (web search, có nguồn) cho thấy tiêu đề gốc tổng quát hoá sai trên 2 điểm cùng lúc.
- Repo đã có **3 theme Remotion** (`collage`, `cinematic`, `poster`), không phải 1 như giả định ở báo cáo
  trước — **cả 3 đều sai ngôn ngữ hình ảnh** cho nhu cầu flat-vector (đọc trực tiếp cả 3 file, xem mục 7.1).
  Cần theme thứ 4, không phải "thêm vào theme có sẵn".
- Phát hiện quan trọng nhất: `derive_texts()` (tự động sinh nhãn chữ từ lời đọc) **chỉ hoạt động đúng với
  tiếng Việt** (regex/từ nối tiếng Việt cứng trong code) — nhưng **đã có đường vòng có sẵn**: field
  `on_screen_text` do người biên tập điền tay sẽ ghi đè, không cần sửa code backend cho pilot tiếng Anh.
- Pilot 45-60s này cần đúng **1 component code mới** (`MechanismCutaway`, tối giản) + **1 theme file mới**
  (`remotion/src/explainer.tsx`) tái dùng gần hết hạ tầng sẵn có. **`HubDiagram` không cần cho đoạn mở đầu
  này — hoãn lại**, lý do ở mục 6.2.

---

## 2. Research brief và nguồn

### 2.1 Về tiêu đề

Đã tra cứu thật (web search, có nguồn dưới đây), không suy luận từ kiến thức sẵn có. Tiêu đề gốc
**"Why Did Arctic Peoples Build Their Homes Out of Snow?"** sai ở 2 điểm:

1. **"Arctic peoples"** quá rộng — igloo (nhà tuyết hình vòm) theo Wikipedia chỉ là tập quán của người Inuit
   vùng **Trung Bắc Cực Canada và khu vực Qaanaaq (Greenland)**; Britannica cho phạm vi khác (từ cửa sông
   Mackenzie đến Labrador) — 2 nguồn không khớp hoàn toàn về ranh giới, nên chỉ nói "một số nhóm Inuit", không
   chốt bản đồ chính xác tuyệt đối. Nhiều nhóm khác (nhiều cộng đồng Yupik, Aleut) dùng nhà bán ngầm lợp cỏ/
   xương cá voi, chỉ dùng tuyết để cách nhiệt bên ngoài, không phải nhà khối tuyết.
2. **"Homes"** sai về bản chất sử dụng — igloo chủ yếu là **nơi trú tạm thời/theo mùa khi đi săn mùa đông**,
   không phải nhà ở chính quanh năm; mùa hè phần lớn dùng lều da động vật.

**Tiêu đề đề xuất: "Why Did Some Inuit Hunters Build Shelters Out of Snow?"** — giữ nghịch lý (tuyết lạnh
nhất lại dùng để giữ ấm), nhưng chính xác hơn: "some" (không phải mọi người Inuit), "hunters" + "shelters"
(không phải nhà ở chính quanh năm).

### 2.2 Câu hỏi trung tâm

Làm sao một bức tường xây từ chính thứ đang cố đóng băng bạn — tuyết — lại trở thành thứ giữ bạn ấm?

### 2.3 Nghịch lý/ngộ nhận có bằng chứng

Ngộ nhận phổ biến: "igloo = nhà điển hình của mọi người Inuit/Bắc Cực". Thực tế (có nguồn, mục 2.6):
igloo là kỹ thuật cụ thể của một số nhóm Inuit vùng Trung Bắc Cực Canada + Qaanaaq, chủ yếu làm nơi trú khi
đi săn mùa đông, không phải nhà ở quanh năm, và không đại diện cho cách ở của mọi dân tộc Bắc Cực.

### 2.4 Cơ chế khoa học chính

Tuyết cách nhiệt tốt không phải vì bản thân nó "ấm", mà vì **không khí bị giữ lại giữa các tinh thể băng**.
Số liệu có nguồn (mục 2.6): tuyết tươi dẫn nhiệt ~0,03 W/(m·K), gần bằng không khí tĩnh (~0,026 W/(m·K));
tuyết nén gió ~0,4 W/(m·K); trong khi **băng đặc dẫn nhiệt ~2,2-2,25 W/(m·K) ở khoảng -10°C** — tức băng đặc
dẫn nhiệt nhanh hơn tuyết nén khoảng 5-70 lần tuỳ mật độ. Kỹ thuật xây còn có bước tạo lớp băng mỏng bên
trong (làm tan rồi đóng băng lại có kiểm soát) để tăng độ bền kết cấu.

### 2.5 Phạm vi lịch sử/văn hoá của tập

Tập trung vào: người Inuit **vùng Trung Bắc Cực Canada** (ví dụ nhóm Netsilik, có phim tư liệu thật ghi lại
— mục 2.6) và khu vực **Qaanaaq, Greenland**; bối cảnh chính là **lều trú khi đi săn mùa đông**, không mở
rộng sang mọi dân tộc Bắc Cực khác (Yupik, Aleut, Sámi dùng kiểu nhà khác hẳn — nêu ngắn gọn để làm rõ ranh
giới, không đi sâu).

### 2.6 5-8 claim cụ thể kịch bản sẽ cần, kèm nguồn

| # | Claim | Nguồn |
|---|---|---|
| 1 | Igloo truyền thống là tập quán của người Inuit vùng Trung Bắc Cực Canada và khu vực Qaanaaq, Greenland — không phải mọi nhóm Inuit | [Wikipedia – Igloo](https://en.wikipedia.org/wiki/Igloo) |
| 2 | Nhiều nhóm Inuit khác (và Yupik, Aleut) dùng nhà bán ngầm lợp cỏ/xương cá voi/da, chỉ dùng tuyết cách nhiệt bên ngoài | [EBSCO Research Starters – Native American Architecture: Arctic](https://www.ebsco.com/research-starters/architecture/native-american-architecture-arctic); [Alutiiq Museum](https://alutiiqmuseum.org/collection/Detail/word/464) |
| 3 | Igloo chủ yếu là nơi trú tạm thời/theo mùa (đi săn mùa đông); mùa hè dùng lều da động vật; một số người Inuit hiện vẫn dựng igloo khi đi săn | [Wikipedia – Igloo](https://en.wikipedia.org/wiki/Igloo); [Britannica Kids – Inuit](https://kids.britannica.com/students/article/Inuit/275079) |
| 4 | Độ dẫn nhiệt: tuyết tươi ~0,03 W/(m·K), không khí tĩnh ~0,026, tuyết nén gió ~0,4 (so với đồng ~384) | [Chem13 News – University of Waterloo](https://uwaterloo.ca/chem13-news-magazine/node/869) |
| 5 | Độ dẫn nhiệt băng đặc ~2,25 W/(m·K) ở khoảng -10°C (đo bằng phương pháp steady-state) | [BNU – Study on thermal conductivity of ice](https://dxwl.bnu.edu.cn/EN/abstract/article/1000-0712/8768) |
| 6 | Quinzhee (gò tuyết đổ đống rồi khoét rỗng) là loại lều tuyết **khác** igloo (khối cắt xếp), gắn với nguồn gốc từ ngữ Athabascan, không phải kỹ thuật Inuit | [New World Encyclopedia – Quinzhee](https://www.newworldencyclopedia.org/entry/Quinzhee) |
| 7 | Người xây tạo lớp băng mỏng bên trong bằng cách làm tan rồi để đóng băng lại có kiểm soát, tăng độ bền; igloo thường gần hình paraboloid hơn bán cầu thật | [Chem13 News – University of Waterloo](https://uwaterloo.ca/chem13-news-magazine/node/869) |
| 8 | Ghi hình tư liệu dân tộc học thật (phim Netsilik) cho thấy người Netsilingmiut dựng igloo khi dừng trại cuối mùa đông | [NFB – At Winter Sea Ice Camp, Part 1](https://www.nfb.ca/film/at_winter_sea_ice_camp_pt_1) |

### 2.7 Điểm chưa chắc chắn / tránh dùng

- **Ranh giới địa lý chính xác của igloo** bị 2 nguồn (Wikipedia vs Britannica) cho khác nhau — chỉ nói
  "vùng Trung Bắc Cực Canada + Qaanaaq", không vẽ bản đồ biên giới chính xác tuyệt đối.
- **Con số "bên trong ấm hơn bên ngoài 20-30°F" lan truyền ở nhiều blog** — các nguồn này trùng lặp nội
  dung giữa nhiều domain khác nhau, không trích được nghiên cứu gốc cụ thể → **không dùng con số này**.
- **Nhà ở người Sámi** chỉ có 1 nguồn chất lượng thấp (lều lavvu) — không đưa vào tập này (ngoài phạm vi
  pilot) nếu chưa có nguồn tốt hơn.
- Không giả định mọi kỹ thuật xây igloo giống nhau qua các thời kỳ/vùng miền — tránh câu khẳng định tuyệt đối.

### 2.8 Thesis 1 câu

*Snow isn't cold because it lacks warmth to give — it insulates because it's mostly trapped air, frozen
in place; understanding that turns "shelter built from the cold itself" from a contradiction into an
engineering choice.*

---

## 3. Opening narration (bản sạch)

> Somewhere on the Arctic sea ice, a hunter kneels down in temperatures that could kill an unprepared
> person within hours. He starts cutting blocks — not from stone, not from wood. From the snow under his
> boots. The same snow that's already trying to freeze him. And out of that, in under an hour, he builds
> a dome just big enough to crawl into, seals the entrance behind him, and settles in for the night.
>
> It sounds backwards: shelter yourself from the cold using the cold itself. But for Inuit hunters of
> Canada's Central Arctic, that block of packed snow wasn't the enemy. It was almost the opposite — one
> of the best insulators within reach, built in under an hour from whatever was already under their feet.
> To see why, you have to look at what's actually hiding inside a single block of snow.

**145 từ** (đếm thật bằng `wc -w`, nằm trong khoảng 130-170 yêu cầu). Ở nhịp 180 từ/phút (chuẩn đo được từ
3 video kênh tham khảo, xem `CHANNEL.md`) ≈ **48.3 giây** — nằm trong khoảng 45-60s mục tiêu. Con số này là
**ước tính theo nhịp chuẩn đã đo**, không phải thời lượng TTS thật — phải đo lại bằng giọng đọc thật trước
khi chốt timing cuối (xem mục 9).

Cố ý **không** dùng cụm "Arctic peoples" hay "homes" trong narration — khớp với tiêu đề đã sửa ở mục 2.1.
Cố ý **không** tiết lộ hết cơ chế khoa học (không khí bị giữ giữa tinh thể băng) — chỉ dừng ở câu hook cuối
cùng, để phần giải thích đầy đủ thuộc về đoạn sau (ngoài phạm vi 45-60s pilot này).

---

## 4. Timed narration beats

| Beat | Narration | Từ | Thời lượng ước tính (180 wpm) | Cộng dồn |
|---|---|---|---|---|
| O1 | "Somewhere on the Arctic sea ice, a hunter kneels down in temperatures that could kill an unprepared person within hours." | 20 | 6.7s | 0.0–6.7 |
| O2 | "He starts cutting blocks — not from stone, not from wood. From the snow under his boots. The same snow that's already trying to freeze him." | 26 | 8.7s | 6.7–15.3 |
| O3 | "And out of that, in under an hour, he builds a dome just big enough to crawl into, seals the entrance behind him, and settles in for the night." | 29 | 9.7s | 15.3–25.0 |
| O4 | "It sounds backwards: shelter yourself from the cold using the cold itself." | 12 | 4.0s | 25.0–29.0 |
| O5 | "But for Inuit hunters of Canada's Central Arctic, that block of packed snow wasn't the enemy." | 16 | 5.3s | 29.0–34.3 |
| O6 | "It was almost the opposite — one of the best insulators within reach, built in under an hour from whatever was already under their feet." | 25 | 8.3s | 34.3–42.7 |
| O7 | "To see why, you have to look at what's actually hiding inside a single block of snow." | 17 | 5.7s | 42.7–48.3 |

Tổng: 145 từ / ~48.3s. **Bắt buộc đo lại bằng `edge_tts` thật** trước khi coi các mốc giây này là cuối cùng
(xem mục 9, tiêu chí chấp nhận).

---

## 5. Scene-by-scene storyboard

6 cảnh, gộp O3+O4 vào cùng 1 cảnh (hình ảnh không đổi, chỉ thêm chữ nhấn mạnh chồng lên).

### S01 — Hunter on the sea ice (0.0–6.7s, narration O1)

| | |
|---|---|
| Viewer sees | Toàn cảnh: một người thợ săn Inuit quỳ trên băng biển, trời xám/tối, không có gì xung quanh ngoài tuyết-băng mênh mông |
| Composition/focal point | Nhân vật lệch 1/3 khung (quy tắc 1/3), nhìn xuống nơi sắp cắt tuyết; không gian trống chiếm phần lớn khung để truyền cảm giác cô lập/khắc nghiệt |
| Diagram/illustration type | Minh hoạ cảnh (không phải diagram) — tranh toàn cảnh |
| Labels/arrows/numbers | Không |
| Animation/reveal | Fade-in nhẹ + pan/zoom chậm (Ken-Burns-style, giữ nguyên cơ chế `useEnter`/zoom đã có trong `PhotoKenBurns`) |
| Transition to next | Cut mềm (fade theo `fadeFrames` đã có cơ chế sẵn trong `Documentary.tsx`) sang S02, zoom gần hơn vào tay |
| AI art hay SVG/React? | **Cần ảnh AI** (minh hoạ nhân vật + bối cảnh, không vẽ hợp lý bằng code) |
| Tái dùng component nào | Cấu trúc **giống `PhotoKenBurns`** (đọc `presets.tsx:63-83`) nhưng cần bản vẽ lại trong theme mới (xem mục 6, 7.1) |
| Component mới cần | Không — chỉ cần bản theme mới của preset đã có |

### S02 — Cutting blocks from snow (6.7–15.3s, narration O2)

| | |
|---|---|
| Viewer sees | Cận cảnh tay cầm dao tuyết (snow knife) cắt một khối tuyết hình chữ nhật từ mặt đất |
| Composition/focal point | Cận cảnh tay + khối tuyết chiếm trung tâm, nền mờ phía sau (người thợ săn chỉ thấy một phần) |
| Diagram/illustration type | Minh hoạ cảnh |
| Labels/arrows/numbers | Không |
| Animation/reveal | Zoom nhẹ theo nhịp cắt, không cần reveal chữ |
| Transition to next | Fade sang S03 |
| AI art hay SVG/React? | Cần ảnh AI |
| Tái dùng | Giống `PhotoKenBurns` |
| Component mới | Không |

### S03 — Dome takes shape + paradox line (15.3–29.0s, narration O3+O4)

| | |
|---|---|
| Viewer sees | Mái vòm igloo đang thành hình, trời sẫm dần; sau đó chữ nhấn mạnh xuất hiện chồng lên cảnh |
| Composition/focal point | Mái vòm ở trung tâm dưới, bầu trời chiếm phần lớn khung trên để chữ overlay có chỗ |
| Diagram/illustration type | Minh hoạ cảnh + 1 dòng chữ nhấn mạnh (không phải diagram) |
| Labels/arrows/numbers | **1 dòng text role `headline`**: "Shelter built from the cold itself." — cueFrame khớp lúc nói "backwards" (O4, giây ~25.0 tương đối cảnh, tức frame ~0 của cảnh nếu cảnh bắt đầu đúng lúc O3 bắt đầu — cần tính lại theo `cue_frame()` thật khi có timeline audio, xem mục 7.3) |
| Animation/reveal | Ảnh giữ nguyên (không Ken Burns mạnh, giữ tĩnh để chữ dễ đọc); chữ `Appear` (dùng lại primitive có sẵn `useEnter`/`Appear` trong `collage.tsx`/`presets.tsx`) |
| Transition to next | Cut sang S04 (đổi hẳn bố cục sang MapZoom) |
| AI art hay SVG/React? | Ảnh nền: AI art. Chữ: **code (SVG/React text)**, không để AI vẽ chữ vào ảnh (đúng nguyên tắc mục 7 của `STRATEGY.md`) |
| Tái dùng | Giống `PhotoKenBurns` (ảnh) + `Appear`/`Highlight` (chữ) — cả 2 primitive đã có sẵn, đọc trực tiếp `collage.tsx` |
| Component mới | Không |

### S04 — Map: Canada's Central Arctic (29.0–34.3s, narration O5)

| | |
|---|---|
| Viewer sees | Bản đồ minh hoạ flat-vector của Bắc Mỹ/Canada, khoanh vùng/pin tại Trung Bắc Cực Canada |
| Composition/focal point | Pin đỏ tại vùng được nhắc tới, nhãn chữ tên vùng |
| Diagram/illustration type | Bản đồ (geographic scoping) |
| Labels/arrows/numbers | 1 text role `label`: "Canada's Central Arctic" |
| Animation/reveal | Zoom vào pin (cơ chế đã có trong `MapZoom`, đọc `presets.tsx:181-208`) |
| Transition to next | Fade sang S05 |
| AI art hay SVG/React? | **Cần ảnh bản đồ thật** (AI art hoặc vector map có sẵn) — **không dùng fallback mặc định của `MapZoom`** khi thiếu `imageSrc` (fallback là đường đồng mức trừu tượng bằng SVG, không phải địa lý thật — xem phát hiện ở mục 7.2). Dùng fallback ở đây sẽ **sai tinh thần "không tổng quát hoá sai địa lý"** mà chính research brief vừa yêu cầu |
| Tái dùng | Giống `MapZoom` (cấu trúc zoom + pin + label đã có sẵn) |
| Component mới | Không — chỉ cần bản theme mới + 1 ảnh bản đồ thật |

### S05 — Thesis statement (34.3–42.7s, narration O6)

| | |
|---|---|
| Viewer sees | Chữ lớn, nền phẳng đơn giản (không cảnh minh hoạ) |
| Composition/focal point | Chữ căn giữa, chiếm phần lớn khung |
| Diagram/illustration type | Text-forward card |
| Labels/arrows/numbers | 1 text role `headline`: "One of the best insulators within reach." |
| Animation/reveal | Chữ xuất hiện theo từng cụm (cơ chế đã có trong `HeadlineImpact`, đọc `presets.tsx:324-355`: chia theo từ, mỗi từ 1 "chip" xuất hiện so le) |
| Transition to next | Cut sang S06 |
| AI art hay SVG/React? | **100% code (SVG/React)**, không cần ảnh AI |
| Tái dùng | Giống `HeadlineImpact` |
| Component mới | Không |

### S06 — Cutaway tease: inside a block of snow (42.7–48.3s, narration O7)

| | |
|---|---|
| Viewer sees | Camera đẩy vào 1 khối tuyết; bề mặt bắt đầu "mở" ra thành mặt cắt lộ các tinh thể băng + túi khí nhỏ — **chỉ hé lộ, chưa giải thích đầy đủ** (phần giải thích đầy đủ thuộc đoạn sau pilot) |
| Composition/focal point | Khối tuyết ở trung tâm, mặt cắt dần hiện ra từ 1 góc |
| Diagram/illustration type | **Sơ đồ cắt lớp (cutaway)** — đúng khái niệm `MechanismCutaway` |
| Labels/arrows/numbers | Chưa có nhãn ở đoạn pilot này (để dành cho đoạn sau) — cảnh này chỉ cần layer hình học, không cần text |
| Animation/reveal | Mặt cắt "mở ra" dần theo `cueFrame`, dừng ở trạng thái hé lộ ~30-40% khi hết 48.3s (cố ý chưa hoàn chỉnh — tạo cảm giác "còn tiếp") |
| Transition to next | Kết thúc đoạn pilot ở đây — điểm nối tự nhiên để tiếp tục phần sau (ngoài phạm vi pilot) |
| AI art hay SVG/React? | **100% code (SVG/React)** — hình học khối tuyết + mặt cắt + túi khí có thể vẽ bằng shape/path, không cần AI vẽ (đúng nguyên tắc giảm lỗi khoa học trong ảnh AI ở `STRATEGY.md` mục 7) |
| Tái dùng | Không preset nào hiện có khớp (gần nhất là `SplitComparison` nhưng đó là so sánh 2 khối tĩnh, không phải 1 khối "mở ra" theo thời gian) |
| Component mới | **Có — `MechanismCutaway`** (spec đầy đủ ở mục 6.1) |

---

## 6. Motion preset specifications

### 6.1 Preset 1 — `MechanismCutaway` (CẦN LÀM cho pilot này)

| Mục | Nội dung |
|---|---|
| **Mục đích** | Minh hoạ cơ chế vật lý bằng cách "mở" một vật thể/bề mặt thành mặt cắt, lộ ra cấu trúc bên trong theo thời gian, khớp lúc lời đọc nhắc tới |
| **Input bắt buộc** | `scene.key` (seed hình dạng ngẫu nhiên tất định, giống cách `rng(scene.key)` đã dùng ở các preset khác); `scene.durationFrames` (điều khiển tốc độ "mở") |
| **Input tuỳ chọn** | `scene.texts[]` (0 hoặc nhiều nhãn `role: "label"` xuất hiện theo `cueFrame`, có thể rỗng — như cảnh S06 ở pilot này); `scene.imageSrc` (nếu có, dùng làm lớp "bề mặt ngoài" thay vì màu phẳng mặc định) |
| **Cấu trúc component** | 3 lớp `AbsoluteFill` chồng nhau: (1) nền màu phẳng theo bảng màu mới (mục 7 `STRATEGY.md`), (2) lớp "bề mặt ngoài" (shape chính, vd khối tuyết) vẽ bằng SVG path, (3) lớp "mặt cắt bên trong" chỉ hiện phần trăm theo `clip-path` tăng dần |
| **Layer ordering** | Nền → bề mặt ngoài → mặt cắt trong (dùng `clip-path: inset()` hoặc `polygon()` tăng dần theo frame) → nhãn chữ (trên cùng, nếu có) |
| **Animation sequence** | `interpolate(frame, [startFrame, startFrame+revealFrames], [0, targetReveal])` — tái dùng chính xác pattern `interpolate(...)` đã thấy ở `TimelineBuild`/`BigNumber` (`presets.tsx`). `targetReveal` mặc định 1.0 (mở hoàn toàn) nhưng **có thể < 1.0** để dừng ở trạng thái hé lộ (như cảnh S06 cần dừng ở ~30-40%) |
| **Timing behavior** | `revealFrames` mặc định = `durationFrames` (mở xuyên suốt cảnh); nếu cảnh có nhãn, mặt cắt nên mở xong trước khi nhãn đầu tiên xuất hiện (nhãn dựa vào `cueFrame` của chính nó, không phụ thuộc animation mở) |
| **Narration → visual mapping** | Nhãn dùng `cueFrame` y hệt cơ chế đã có (`cue_frame()` trong `render_plan.py`, đã đọc — khớp theo từ đầu tiên của narration thật qua timeline audio thật). Việc "mở" mặt cắt **không** cần khớp từ cụ thể — chỉ cần mở mượt trong suốt cảnh, vì không có 1 từ đơn lẻ nào đại diện cho "đang mở dần" |
| **Text/annotation handling** | Nhãn vẽ bằng component `Label` đã có sẵn (`presets.tsx`, dùng lại nguyên hàm), không viết lại |
| **Responsive behavior** | Cố định khung 1920×1080 (đúng theo `WIDTH, HEIGHT = 1920, 1080` trong `render_plan.py` — hệ thống hiện không responsive đa kích thước, giữ nguyên quy ước) |
| **Error/fallback behavior** | Nếu `scene.texts` rỗng: không render nhãn, chỉ còn animation mở mặt cắt (đúng trường hợp S06 ở pilot). Nếu `scene.imageSrc` null: dùng màu phẳng mặc định cho lớp bề mặt ngoài thay vì crash (theo đúng pattern `scene.imageSrc ? <Photo/> : <Placeholder/>` đã thấy lặp lại ở mọi preset hiện có) |
| **Ví dụ cụ thể (snow)** | Lớp ngoài: khối tuyết trắng-xanh nhạt hình hộp bo góc. Mặt cắt: hiện dần 1 góc lộ ra các hình đa giác nhỏ bất quy tắc (tinh thể băng, vẽ bằng `rng(scene.key)` tất định giống cách `Contours`/`EvidenceBoard` đã tạo hình ngẫu nhiên có seed) xen giữa là các khoảng trống nhỏ màu nhạt hơn (túi khí) |

### 6.2 Preset 2 — `HubDiagram` (HOÃN LẠI, chỉ đặc tả trên giấy)

**Lý do hoãn:** storyboard pilot 45-60s (mục 5) **không có cảnh nào cần** "1 vật trung tâm làm nhiều việc,
nối tới nhiều nhãn". Theo đúng cấu trúc 10-beat đã xác nhận ở `CHANNEL.md`, beat "hub đa chức năng" chỉ xuất
hiện ở **giữa-cuối tập đầy đủ** (beat 6/10), xa ngoài phạm vi 1 đoạn mở đầu. Implement bây giờ là xây trước
khi có use case thật kiểm chứng — vi phạm trực tiếp ràng buộc "Do not implement both presets automatically
before proving they are needed". Đặc tả dưới đây để dùng khi làm tập đầy đủ (P1), **không code ở P0**.

| Mục | Nội dung (đặc tả, chưa code) |
|---|---|
| **Mục đích** | Minh hoạ 1 vật/hệ thống trung tâm phục vụ nhiều chức năng cùng lúc, nối tới N nhãn xung quanh bằng đường kẻ |
| **Input bắt buộc** | `scene.key`; `scene.texts[]` với ít nhất 2 phần tử role `label` (mỗi nhãn = 1 chức năng) |
| **Input tuỳ chọn** | `scene.imageSrc` (hình vật trung tâm, nếu không có thì vẽ shape placeholder) |
| **Cấu trúc component** | Vật trung tâm ở giữa khung; N nhãn bố trí vòng quanh (layout toả tròn, số lượng N quyết định bán kính/góc chia đều — giống cách `EvidenceBoard` đã tính `LAYOUTS` theo số lượng card, đọc `presets.tsx:285-292`) |
| **Node/connection representation** | Mỗi nhãn nối về vật trung tâm bằng 1 đường SVG `<line>` hoặc `<path>` cong nhẹ, vẽ dần theo `cueFrame` của nhãn đó (interpolate độ dài đường vẽ, giống cách `EvidenceBoard` vẽ đường ghim bằng `drawn` ratio, đọc `presets.tsx:296,301-305`) |
| **Animation sequence** | Mỗi nhãn + đường nối xuất hiện so le theo `cueFrame` riêng (tái dùng `Appear`), không đợi tất cả cùng lúc |
| **Timing behavior** | Nhãn xuất hiện đúng lúc narration nhắc tới chức năng đó — y hệt cơ chế `cueFrame` đã kiểm chứng |
| **Text/annotation handling** | Mỗi nhãn 1 cụm ngắn (không phải câu dài) — giống `EvidenceBoard` giới hạn độ dài theo `fitBox` |
| **Responsive** | Cố định 1920×1080, giống mọi preset khác |
| **Error/fallback** | Nếu <2 nhãn: không nên dùng preset này (không đủ "nhiều chức năng" để vẽ hub) — validate ở tầng storyboard, không phải ở component |
| **Ví dụ liên quan pilot** | **Không áp dụng cho pilot này** — nếu làm tập đầy đủ về igloo, hub có thể là "1 khối tuyết phục vụ: cách nhiệt, vật liệu có sẵn tại chỗ, dễ sửa khi nứt, không cần mang vác" — nhưng đây chỉ là ví dụ minh hoạ cho P1, chưa xác nhận bằng research thật |

---

## 7. Verified repository findings

> Đọc trực tiếp trong phiên này: `remotion/src/{schema.ts,Documentary.tsx,Root.tsx,presets.tsx,cinematic.tsx,
> poster.tsx,collage.tsx}`, `remotion/package.json`, `backend/app/modules/documentary/{storyboard.py,
> render_plan.py}`. Phát hiện khác với giả định ở `STRATEGY.md` được đánh dấu **[KHÁC BÁO CÁO TRƯỚC]**.

| # | Phát hiện | Nguồn (file:dòng) |
|---|---|---|
| 1 | **[KHÁC BÁO CÁO TRƯỚC]** Có **3 theme** (`collage`, `cinematic`, `poster`), không phải 1. Cả 3 dùng chung 1 schema (`Scene`/`SceneText`) và chung tập tên preset, nhưng mỗi theme tự vẽ lại hoàn toàn | `remotion/src/schema.ts:46`; `Documentary.tsx:11` |
| 2 | `poster` theme gộp **toàn bộ 9 preset về 1 component duy nhất** (`PosterScene`) — không có khả năng vẽ diagram/cutaway/hub, chỉ ảnh full-bleed + chữ cắt dán + confetti. **Không dùng được** làm nền cho theme mới | `remotion/src/poster.tsx:136-168` |
| 3 | **[KHÁC BÁO CÁO TRƯỚC]** `MapZoom` khi **không có `imageSrc`** tự vẽ fallback là đường đồng mức trừu tượng ngẫu nhiên có seed (component `Contours`), **không phải bản đồ địa lý thật** — pin cũng ở toạ độ cố định hard-code, không gắn với kinh độ/vĩ độ thật | `remotion/src/presets.tsx:160-208` |
| 4 | **[KHÁC BÁO CÁO TRƯỚC, QUAN TRỌNG]** `derive_texts()` (tự sinh nhãn chữ từ narration khi không có `on_screen_text`) **viết riêng cho tiếng Việt**: regex nhận diện danh từ riêng dựa comment "các ký tự tiếng Việt", tập từ nối `_CONNECTORS = {"năm","vào","từ",...}` toàn tiếng Việt, `_UNIT_AFTER_YEAR` khớp từ "người/tấn/km" tiếng Việt. **Không hoạt động đúng với narration tiếng Anh** | `backend/app/modules/documentary/render_plan.py:55,99-128,131-185` |
| 5 | **Có đường vòng có sẵn cho phát hiện #4**: `build_manifest()` ưu tiên `sc.on_screen_text` (do người biên tập điền tay) trước, chỉ fallback `derive_texts()` khi rỗng. **Pilot tiếng Anh chỉ cần điền tay `on_screen_text`, không cần sửa code backend** | `render_plan.py:270-271` |
| 6 | Cơ chế đồng bộ lời đọc thật: `cue_frame()` khớp từ đầu tiên của 1 nhãn (`anchor`) với timeline từ thật (có timestamp), trả về frame tương ứng; nếu không khớp được thì dùng stagger cố định — **đây là cơ chế thật, đã kiểm chứng**, không phải giả định | `render_plan.py:188-196` |
| 7 | Theme được chọn bằng **3 nhánh if/else lặp lại ở 3 chỗ trong cùng 1 file** `Documentary.tsx`: chọn component theo preset (dòng 11), chọn subtitle renderer (dòng 26-27), chọn màu nền (dòng 54). Thêm theme thứ 4 cần sửa **cả 3 chỗ** trong file này | `remotion/src/Documentary.tsx:11,26-27,54` |
| 8 | Danh sách theme + preset bị **khai trùng ở cả 2 phía** (không dùng chung 1 nguồn sự thật): TS `THEMES`/`PRESET_NAMES` trong `schema.ts`, Python `THEMES` trong `render_plan.py` + `PRESETS` trong `storyboard.py`. Thêm theme/preset mới phải sửa **cả 4 chỗ** | `remotion/src/schema.ts:6-16,46`; `render_plan.py:49`; `storyboard.py:34-38` |
| 9 | `DATA_PRESETS = {"TimelineBuild","BigNumber","MapZoom"}` — tập preset được phép tự sinh nội dung khi không có ảnh. `MechanismCutaway` không cần ảnh (mục 6.1) nên nên được thêm vào tập này | `render_plan.py:45` |
| 10 | Công cụ preview thật sự tồn tại và không cần chạy backend: `npm run studio` (Remotion Studio, chỉnh `defaultProps` thủ công để xem live), `npm run render:smoke`, `npm run typecheck` | `remotion/package.json:7-9` |
| 11 | Khung hiển thị cố định 1920×1080 @ 30fps, không có cơ chế responsive đa kích thước — xác nhận đúng giả định trước, không phải phát hiện mới | `remotion/src/Root.tsx:9`; `render_plan.py:40-41` |

**Chưa đọc / UNKNOWN (cần xác nhận trước khi cam kết ở P1):** `voice/timing.py` (độ chính xác khớp từ thật
với edge_tts tiếng Anh); `documentary/alignment.py`/`align_whisper.py` (cơ chế lấy timestamp audio thật —
tên file gợi ý dùng whisper để align, nhưng chưa đọc source để xác nhận); quy trình API thật để tạo 1 project
documentary từ đầu (đã đọc logic, chưa thử gọi API thật trong phiên này).

---

## 8. Minimal implementation plan (file path đã verify)

### P0 — bắt buộc để render được đoạn pilot 45-60s

| # | File | Thay đổi | Lý do | Tái dùng được gì | Rủi ro | Cách test |
|---|---|---|---|---|---|---|
| 1 | `remotion/src/schema.ts` | Thêm `"flatvector"` vào mảng `THEMES` (dòng 46); thêm `"MechanismCutaway"` vào `PRESET_NAMES` (dòng 6-16) | Theme/preset mới phải được zod chấp nhận, nếu không manifest sẽ bị validation reject | Giữ nguyên cấu trúc mảng hằng số đã có | Thấp — chỉ thêm phần tử, không đổi type nào khác | `npm run typecheck` phải pass |
| 2 | `remotion/src/theme_explainer.ts` (file mới) | Định nghĩa `COLORS`/`FONTS`/`MOTION` riêng cho flat-vector (bảng màu mục 7 `STRATEGY.md`) — **không sửa `theme.ts` hiện có** vì template khác (Vox gốc) đang phụ thuộc nó | Tách riêng theo đúng ràng buộc "không phá theme cũ" | Copy cấu trúc từ `theme.ts` đã có (chỉ đổi giá trị) | Thấp | Import thử trong Storybook/Remotion Studio, xem màu đúng bảng đề ra |
| 3 | `remotion/src/explainer.tsx` (file mới) | Component mới cho theme `flatvector`: `FvPhoto` (dựa `PhotoKenBurns`), `FvMap` (dựa `MapZoom`, **bắt buộc có `imageSrc` thật**, không dùng `Contours` fallback — xem phát hiện #3), `FvHeadline` (dựa `HeadlineImpact`), `MechanismCutaway` (mới, spec mục 6.1) + `EXPLAINER_COMPONENTS` map đủ 10 key (9 preset cũ + `MechanismCutaway`) để tránh `undefined` component nếu storyboard lỡ gán preset khác | Đây là phần code thật sự mới duy nhất cần cho pilot | Tái dùng `useEnter`/`Appear`/`Label`/`Highlight`/`rng` từ `collage.tsx` nguyên vẹn | Trung bình — là file lớn nhất trong plan | Render từng scene riêng trong Remotion Studio (`npm run studio`), so khớp với storyboard mục 5 bằng mắt |
| 4 | `remotion/src/Documentary.tsx` | Sửa 3 nhánh if/else (dòng 11, 26-27, 54) thêm điều kiện `theme === "flatvector"` | Đây là nơi DUY NHẤT dispatch theme — không sửa thì theme mới không bao giờ được gọi | Giữ nguyên 2 nhánh cũ không đổi | Thấp nếu chỉ thêm nhánh, không sửa nhánh cũ | Set `theme: "flatvector"` trong `defaultProps` ở `Root.tsx` tạm thời để test, xem đúng component mới được chọn |
| 5 | `backend/app/modules/documentary/render_plan.py` | Thêm `"flatvector"` vào `THEMES` (dòng 49); thêm `"MechanismCutaway"` vào `DATA_PRESETS` (dòng 45, vì preset này không bắt buộc cần ảnh — mục 6.1) | Backend phải chấp nhận giá trị theme/preset mới khi build manifest, nếu không sẽ raise lỗi validate | Giữ nguyên toàn bộ hàm khác | Thấp | Gọi `RenderParams(theme="flatvector")` thử trong 1 script/test nhỏ, không raise lỗi |
| 6 | `backend/app/modules/documentary/storyboard.py` | Thêm `"MechanismCutaway"` vào `PRESETS` (dòng 34-36) | `preset in PRESETS` check ở nhiều nơi (vd `render_plan.py:272,345`) sẽ reject preset lạ nếu không thêm | Giữ nguyên | Thấp | Gán `visual_preset="MechanismCutaway"` cho 1 scene test, xác nhận không bị review-issue "unknown_preset" (`render_plan.py:346`) |
| 7 | Kịch bản + `on_screen_text` cho 6 cảnh (mục 5) | Điền tay `on_screen_text` cho S03 (headline), S04 (label địa danh), S05 (headline) — **không cần code mới**, chỉ nhập liệu | Né hoàn toàn vấn đề `derive_texts()` tiếng Việt (phát hiện #4) | Dùng đúng field đã có sẵn | Thấp | Nhập xong, build manifest, xem `texts[]` trong JSON đúng như mục 5 |

### P1 — sau khi pilot đạt mới làm (mở rộng thành tập 8-9 phút)

| # | Việc | Lý do chỉ làm sau pilot |
|---|---|---|
| 1 | Code đầy đủ `HubDiagram` (spec mục 6.2) | Chỉ cần khi viết hết kịch bản đầy đủ và thật sự có 1 beat "hub đa chức năng" — storyboard pilot hiện tại không có |
| 2 | Vẽ đầy đủ `MechanismCutaway` với label + mở 100% (pilot chỉ cần mở ~30-40%, không label) | Pilot chỉ cần chứng minh component render được, chưa cần hoàn thiện animation đầy đủ |
| 3 | Ảnh AI thật cho 3 cảnh minh hoạ (S01, S02, S03) + ảnh bản đồ thật cho S04 | Theo đúng ràng buộc "không generate hàng loạt ảnh AI trước khi xác nhận hướng hình ảnh" — pilot có thể test bằng placeholder/phác thảo trước |
| 4 | Thêm `on_screen_text` tự động hoá / sửa `derive_texts()` hỗ trợ tiếng Anh | Chỉ đáng làm nếu quyết định sản xuất nhiều tập tiếng Anh — pilot điền tay đủ dùng |

### P2 — hoãn dài hạn (không nằm trong yêu cầu lần này, chỉ ghi nhận)

Đồng bộ 4 nguồn sự thật bị trùng lặp (phát hiện #8) thành 1 config dùng chung giữa TS và Python — chỉ đáng
làm khi đã thêm ≥3 theme/preset mới và việc sửa 4 chỗ mỗi lần bắt đầu gây lỗi thật (không làm trước khi có
bằng chứng cần thiết, đúng nguyên tắc "no framework before a real use case proves it").

---

## 9. Pilot acceptance checklist

| Tiêu chí | Loại | Cách kiểm tra |
|---|---|---|
| Mọi claim trong narration truy được về đúng 1 trong 8 nguồn ở mục 2.6 | Kỹ thuật/khách quan | Đối chiếu tay từng câu narration với bảng claim — không có câu nào không truy nguồn được |
| Không còn cụm "Arctic peoples"/"homes" hoặc khẳng định tổng quát hoá quá mức | Kỹ thuật/khách quan | Đọc lại narration, so với mục 2.1 |
| `npm run typecheck` pass sau khi thêm theme/preset mới | Kỹ thuật/khách quan | Chạy lệnh thật |
| 6 cảnh ở mục 5 render đúng trong Remotion Studio, không lỗi runtime | Kỹ thuật/khách quan | `npm run studio`, xem từng `Sequence` |
| Nhịp đọc TTS thật (`edge_tts`, giọng tiếng Anh) lệch khỏi ước tính 48.3s bao nhiêu % | Kỹ thuật/khách quan | Đo thời lượng file audio thật sau khi synth, so với mục 4 — **không đặt ngưỡng % tuỳ ý trước, chỉ ghi nhận số đo thật** |
| Nhãn chữ xuất hiện đúng lúc được nhắc tới trong lời đọc (S03, S04, S05) | Kỹ thuật/khách quan | Xem video, đối chiếu `cueFrame` tính được từ `cue_frame()` thật với audio thật |
| Caption đọc được trên khung hình (tương phản, không tràn) | Kỹ thuật/khách quan | Xem thử trên màn hình điện thoại giả lập (thu nhỏ khung xem) |
| Render không lỗi, xuất được file cuối | Kỹ thuật/khách quan | Chạy render thật (preview trước, sau đó bản scale thấp) |
| Chi phí thật đo được qua `ai/cost_estimator.py` (nếu có gọi AI image) nằm trong 10 USD | Kỹ thuật/khách quan | Chạy công cụ đã có, không tự đoán |
| Nhất quán ngôn ngữ hình ảnh flat-vector giữa 6 cảnh (bảng màu, nét vẽ) | **Chủ quan/sáng tạo** | Người làm kênh tự xem, đánh giá bằng mắt theo bảng quy tắc mục 7 `STRATEGY.md` |
| Cảm giác "nghịch lý mở đầu" có đủ hấp dẫn để xem tiếp không | **Chủ quan/sáng tạo** | Cho người khác xem thử (không phải người đã biết chủ đề), hỏi phản ứng thật |
| Component `MechanismCutaway`/theme mới có tái dùng được cho cảnh khác không chỉ riêng chủ đề tuyết | **Chủ quan, cần P1 mới trả lời đầy đủ** | Thử gán cho 1 kịch bản/chủ đề khác (vd thermal mass bếp Nga) xem có hợp lý không — ngoài phạm vi pilot này |

Công cụ tự động sẵn có **tái dùng được**: `quality/analyzer.py`, `postqa/analyzer.py` (đã xác nhận ở
`STRATEGY.md` mục 8.1, không lặp lại chi tiết ở đây). Các tiêu chí còn lại **chưa có check tự động**, cần
soát tay — không giả định có công cụ nào tự động hoá được đến khi thật sự kiểm tra.

---

## 10. Single next action

**Chạy `npm run studio` trong `remotion/`, tạo 1 manifest thủ công (JSON nhỏ, không qua backend) cho đúng
6 cảnh ở mục 5 với placeholder màu phẳng thay ảnh AI (chưa cần gen ảnh thật), và xác nhận bằng mắt thật rằng
layer/animation của `MechanismCutaway` (mục 6.1) hoạt động đúng ý trước khi viết bất kỳ dòng code production
nào khác.** Đây là bước rẻ nhất để kiểm tra rủi ro lớn nhất (component mới có vẽ đúng cảm giác mong muốn
không) trước khi đầu tư thời gian vào ảnh AI, giọng đọc thật, hay sửa 6 file ở mục 8.
