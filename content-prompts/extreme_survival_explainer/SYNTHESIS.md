# SYNTHESIS — tổng hợp điểm hay của nhiều kênh để làm bản sắc riêng

> Mục tiêu (theo yêu cầu 2026-10-14): **không theo 1 kênh nào**; lấy kỹ thuật chuyển giao được từ từng kênh,
> bỏ phần chỉ là đặc thù kênh, rồi ghép thành công thức riêng. Nhãn: **FACT** (đo/đọc trực tiếp) /
> **INFERENCE** (suy luận từ FACT) / **UNKNOWN** (chưa có dữ liệu).
>
> - **Kênh A** = 3 video: nhà giấy Nhật, bếp Nga, che mặt sa mạc → xem [`CHANNEL.md`](CHANNEL.md).
> - **Kênh B** = watermark "BEFORE CIVILIZATION", 2 video: *The Worst Place to Spend One Night During the Ice Age*
>   (33:09) và *How Did Ancient Humans Sleep Through Endless Rain* (26:19).
> - Chưa có số view/retention/thumbnail của kênh B → **UNKNOWN** mức thành công; mọi điểm dưới đây chỉ là
>   kỹ thuật quan sát được, không phải bằng chứng "cái này làm nên view".
> - Mọi claim lịch sử/khoa học trong video của cả hai kênh **chưa được tôi kiểm chứng** (trừ 1 điểm ở mục 5).

## 1. Số đo thật (từ transcript faster-whisper, đếm `wc -w`)

| Video | Kênh | Thời lượng | Số từ | Từ/phút |
|---|---|---|---|---|
| Nhà giấy Nhật | A | 13:54 | 2.498 | 179.8 |
| Bếp Nga | A | 14:24 | 2.568 | 178.3 |
| Che mặt sa mạc | A | 11:10 | 2.016 | 180.5 |
| Ice Age one night | B | 33:09 | 4.989 | 150.5 |
| Ngủ qua mưa | B | 26:19 | 4.209 | 159.9 |

FACT: A nhanh và đồng đều (~180 wpm, 11–14 phút); B chậm hơn (~150–160 wpm) và dài gấp 2–3 lần.

## 2. Bảng đối chiếu

| Trục | Kênh A (flat-vector explainer) | Kênh B (Before Civilization) |
|---|---|---|
| Khung kể | 1 nguyên lý trung tâm, 3–4 cơ chế con | **Chuỗi "trạm/đêm" theo thời gian**, mỗi trạm 1 địa điểm khảo cổ có tên (Rain: 7 trạm từ 1,8 triệu năm đến 3180 TCN) |
| Mở đầu | Cảnh lịch sử cụ thể + nghịch lý | **Hành động đời thường hôm nay** (đắp chăn, nằm nghe mưa) → "việc này cổ 900.000 năm" |
| Câu hỏi trung tâm | Nêu rồi giải thích dần | **Nêu rồi giữ đáp án rất lâu** (Ice Age: "nơi tệ nhất không phải nơi bạn nghĩ", trả lời ở ~26:00/33:09) |
| Nguồn nêu trong lời | Không có người/nghiên cứu nào được gọi tên trong 3 transcript (0 dòng khớp) | **Gọi tên người + năm + tạp chí** (Leakey, de Lumley, Wadley/Science, Samson & Nunn 2017, Pryor 2020, Bello 2011…): 9 + 6 dòng khớp |
| Thừa nhận bất định | 2 dòng (chỉ video Nhật) | 6 + 5 dòng; **biến bất định thành kịch tính** ("tôi sẽ không giả vờ nó đã chốt chỉ để câu chuyện gọn") |
| CTA lời nói | Không có | **1 lần ở ~15–16% thời lượng** (Rain 237s, Ice Age 317s), đặt ngay sau trạm đầu + cliffhanger |
| Chốt | "next time you…" + câu thơ hoá | **Bookend**: quay lại cái chăn/tiếng mưa của mở đầu; ẩn dụ "cuộc chạy tiếp sức dài nhất" / "câu chưa hoàn tất lâu đời nhất" |
| Hình ảnh | Flat-vector, diagram mũi tên/nhãn, sơ đồ cắt lớp, hub | **Tranh minh hoạ AI có texture**, nhân vật stickman đầu tròn + người tiền sử mặc da; logo góc phải; overlay nút Subscribe/Like (≥2 khung ở Ice Age) |
| Diagram có nhãn | Nhiều | Chưa thấy trong khung lấy mẫu 1/phút — **không đủ để kết luận là không có** |
| Nhân vật | Stickman làm minh hoạ + người thời đại | Stickman làm "người xem tự nhập vai" xuyên suốt, lẫn cảnh hiện đại |

## 3. Điểm chung (khả năng cao là nền tảng thể loại)

1. **Mô hình tư duy bị lật.** A: "kẻ thù thật là hơi ẩm/khô, không phải lạnh". B: "người tiền sử không phải kẻ lượm lặt khổ sở".
   Cả hai đều có câu "hình dung của bạn sai/ngược".
2. **Gọi thẳng người xem ("you")**, thì hiện tại, bắt người xem "đứng" trong cảnh ("Here's your night at…").
3. **Chốt bằng callback về hình ảnh mở + liên hệ đời sống đêm nay của người xem.**
4. **Gom kết quả rời rạc thành 1 hệ thống/chuỗi** (A: hub đa chức năng; B: chuỗi/ladder).
5. **Câu chuyển tổng kết kiểu "so let's step back / so here's the honest answer".**
6. **Giọng đọc đều, nhịp đặn, câu ngắn-xen-dài**, không nhạc dẫn chuyện lộ liễu (chưa phân tích audio nhạc nền — UNKNOWN).

## 4. Điểm riêng đáng mượn

**Từ A**
- Diagram code-vẽ có nhãn: cắt lớp cơ chế, hub, so sánh song song, timeline. Biến cơ chế vật lý thành hình nhớ được.
- Nhịp đặc ~180 wpm → video 8–9 phút vẫn chứa 1 nguyên lý trọn vẹn (rẻ hơn sản xuất).
- 1 nguyên lý trung tâm nói thẳng bằng 1 câu rồi lặp lại.

**Từ B**
- **Mở bằng việc người xem làm tối nay** → tự nhiên gắn hiện tại với quá khứ, bookend dễ.
- **Giữ đáp án (open loop) + hứa số lượng** ("tám đêm, tám nơi") để có lý do xem tiếp. Nhắc "chúng ta sẽ quay lại, đó là toàn bộ đáp án" trước khi trả lời.
- **Nêu tên nguồn thật** (người, năm, nơi công bố) → tăng độ tin cậy, đồng thời là cổng kiểm chứng cho chính mình.
- **Bất định như kịch tính**: "Leakey có thể sai", "ghost tan biến vào sáng" — biến việc thiếu bằng chứng thành câu chuyện, không giả vờ chắc chắn.
- **CTA 1 lần, ở ~15%, gắn với cliffhanger** thay vì xin cuối video.
- **Cảnh "đứng trong đêm đó"**: 1 đoạn vignette thì hiện tại tại mỗi địa điểm (nhiệt độ, gió, cái gì chạm da) — rất hợp hình ảnh.

## 5. Rủi ro / điểm KHÔNG nên mượn nguyên xi

| Điểm | Vì sao | Nhãn |
|---|---|---|
| **Câu "ngược hết": "không phải X, không phải Y, không phải Z — mà là W (kim khâu / nước)"** | Loại trừ có tính tu từ rồi gán nguyên nhân đơn. Ice Age gán việc Anh được tái định cư cho cây kim, nhưng cũng nêu khí hậu ấm lên ~14.700 năm trước; video không cho thấy cách tách 2 nguyên nhân | INFERENCE — cần kiểm chứng riêng trước khi bắt chước kiểu "single cause" |
| **Con số "25 lần"** | Nguồn tra được (Univ. Michigan, Fire Engineering) nói **người ngâm trong nước mất nhiệt nhanh ~25 lần so với không khí tĩnh cùng nhiệt độ** — là con số xấp xỉ. Video Ice Age nói đúng dạng này, nhưng video Rain nói "da ướt mất nhiệt nhanh hơn da khô ~25 lần" (không khớp) và Ice Age còn kết luận "chiếc da ướt ở +2°C giết nhanh hơn da khô ở −50°C" — chưa tìm thấy nguồn | FACT (con số xấp xỉ có nguồn: [UMich](https://websites.umich.edu/~lpt/Divegeek/notcold.htm), [Fire Engineering](https://www.fireengineering.com/technical-rescue/immersion-hypothermia-and-winter-water-operations/)); câu kết luận = UNKNOWN |
| **Cụm gây nhớ lặp liên tục** ("here's the thing", "sit with that", "let that land", "read that again": ~12 và ~14 dòng khớp trong 2 video) | 26–33 phút lặp cùng cụm dễ gây nhàm/giống văn AI; người xem lâu sẽ nhận ra | INFERENCE |
| **Hứa "8 đêm" nhưng đếm được ~6–7 địa điểm có tên** (tuỳ cách tính) | Hứa số lượng mà thiếu là rủi ro mất tin cậy | FACT (đếm tay trên transcript), nguyên nhân UNKNOWN |
| **Chi tiết gây sốc** (ăn thịt người ở Gough's Cave) | Có thể ảnh hưởng quảng cáo/kiếm tiền — chưa kiểm tra chính sách | INFERENCE |
| **Watermark + nút Subscribe vẽ vào hình** | Là nhận diện riêng của kênh B; copy sẽ giống bản sao | — |

## 6. Đề xuất blend (mặc định, có thể đổi)

1. **Hook**: hành động đời thường của người xem **tối nay** (từ B) + 1 con số/nghịch lý cụ thể về điều kiện khắc nghiệt (từ A).
2. **Độ dài**: tập đầu 8–9 phút theo kiểu A (1 nguyên lý) nhưng **chèn 1 "trạm" gọi tên nguồn thật** + 1 câu bất định thẳng thắn (từ B). Chuỗi nhiều trạm 20+ phút chỉ thử sau khi tập ngắn chạy được.
3. **Đáp án**: không phải mọi tập đều giữ đáp án 80% thời lượng; thử giữ đến ~50–60% ở tập 8–9 phút.
4. **Nguồn**: gọi tên 2–3 người/nghiên cứu **đã kiểm tra** trong lời (khớp với bảng claim của pipeline `claims/sources`), không gọi tên nguồn chưa kiểm.
5. **CTA**: 1 lần ở ~15% (từ B), viết lại bằng giọng riêng, gắn với beat kế tiếp, không dùng nút vẽ trong hình.
6. **Hình ảnh**: **cảnh kể chuyện** (người ở nơi chốn) dùng minh hoạ AI một style cố định; **cảnh giải thích** dùng diagram code-vẽ có nhãn (A). Nhãn chữ luôn do code vẽ. Đây là quyết định chưa kiểm chứng — thử trong pilot.
7. **Chốt**: bookend về hành động mở đầu + liên hệ tối nay, nhưng **viết câu riêng, không dùng lại cụm "next time you…"/"relay race"** của các kênh gốc.
8. **Giọng/nhịp**: thử ~165–175 wpm (giữa A và B); đo bằng TTS thật rồi chỉnh.

## 7. Điều này ảnh hưởng gì tới tài liệu hiện có (chưa sửa, chờ bạn xác nhận)

- [`PILOT.md`](PILOT.md) mở bằng cảnh thợ săn (kiểu A). Có thể thử bản thứ 2 mở bằng hành động tối nay (kiểu B) rồi so 2 bản.
- `PILOT.md` chưa có câu thừa nhận bất định/nguồn gọi tên; đoạn 45–60 giây có thể thêm 1 câu về ranh giới địa lý còn tranh cãi (đã có trong research brief mục 2.7).
- [`STRATEGY.md`](STRATEGY.md) coi 3 video A là "kênh tham khảo"; mục 4.4 (view cao 1 video không suy ra công thức) vẫn đúng và còn mạnh hơn khi có kênh B.

## 8. UNKNOWN cần xác định

- View/retention/thumbnail của kênh B, và liệu A và B có cùng đối tượng/ngách không.
- Kênh B có phải nội dung tự động hoá hoàn toàn không (không đủ bằng chứng).
- Liệu cấu trúc "chuỗi trạm" có giữ chân thật tốt hơn "1 nguyên lý" — chỉ đo được sau khi đăng.
- Âm nhạc/âm thanh nền của cả hai kênh chưa phân tích.
