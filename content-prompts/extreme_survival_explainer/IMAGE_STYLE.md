# Ảnh AI cho series "extreme survival" — flat-vector, đặt trong khung collage

> Dựng trên theme `collage` có sẵn (`vox_documentary_template/RULES.md` mục 8) — khung giấy rách/băng
> keo là lớp trình bày, **không đổi** style ảnh bên trong. Ảnh ở đây là **flat-vector**, khác hẳn Baroque
> (`vox_documentary_template/IMAGE_STYLE.md`) hay poster collage của Biblical Figures — xem lý do chọn ở
> `STRATEGY.md` mục 7, quyết định tái dùng engine ở `TEMPLATE.md`. Ảnh màu → nhớ **tắt "Ảnh đen trắng"**
> khi render (mặc định tắt, không cần đổi).

## 1. Khi nào dùng ảnh nào

| Cảnh cần | Dùng |
|---|---|
| Kể chuyện (người, bối cảnh, hành động cụ thể) | Ảnh AI flat-vector (mục 2-3) |
| Số liệu, nguyên lý khoa học, bản đồ, so sánh, timeline | Không cần ảnh — cảnh đồ họa do Remotion vẽ (`BigNumber`/`EvidenceBoard`/`MapZoom`/`TimelineBuild`/`SplitComparison`/`HeadlineImpact`) |
| Chuỗi nhiều địa điểm không liên hệ (hội tụ văn hoá) | `TacticalMap` — không cần ảnh, chỉ cần tên địa điểm trong `on_screen_text` |
| "Bên trong X là gì" (cutaway) | **1 ảnh** AI hé lộ một phần cấu trúc, zoom bằng `PhotoKenBurns` (xem mục 4) — `SplitComparison` chỉ nhận 1 ảnh + 1 dòng chữ, không phải 2 ảnh |

## 2. Khối phong cách (dán nguyên vào cuối mỗi prompt)

```
Flat vector illustration, thick uniform black outlines (~5px at 1920px width), solid flat colors, no
gradients, no shading, no texture, simple geometric shapes, characters with round heads, dot eyes, no
nose, minimal detail. 16:9 composition, large empty area near the top and bottom for text overlay
(captions + on-screen labels render there). IMPORTANT STYLE RESTRICTIONS: no text, no letters, no
numbers, no watermark, not photorealistic, not 3D render, not a painting, no gradient shading.
```

## 3. Bảng màu mã hoá dữ liệu (cố định xuyên series, `STRATEGY.md` mục 7)

| Màu | Ý nghĩa | Dùng khi |
|---|---|---|
| Đỏ-cam | Nhiệt / nguy hiểm | Chủ đề nóng, lửa, cảnh báo |
| Xanh dương | Lạnh / nước | Chủ đề Bắc Cực, mưa, biển |
| Vàng | Năng lượng / ánh sáng | Mặt trời, lửa trại, đèn |
| Xám | Vật liệu trung tính | Đá, gỗ, kim loại không liên quan nhiệt |

Mỗi tập chọn 2-3 tông nền theo bối cảnh khí hậu (vd tập Bắc Cực: xanh dương-xám-trắng; không dùng đỏ-cam
trừ khi cảnh thật sự nói về lửa/nhiệt).

## 4. Công thức prompt một cảnh

```
<chủ thể và hành động cụ thể>, <bối cảnh>, <1-2 màu chủ đạo từ mục 3>. <KHỐI PHONG CÁCH ở mục 2>
```
- Giữ cảnh **đơn giản** — càng nhiều chi tiết, AI càng lệch khỏi flat (xu hướng tự thêm bóng đổ/gradient).
- Nhân vật: tỉ lệ đầu-thân cố định, mắt chấm, không vẽ mũi — dùng lại đúng mô tả này ở mọi lần gen để
  nhất quán phong cách (không phải 1 bộ asset tái dùng, mà 1 "house style" được brief lại mỗi lần — xem
  `CHANNEL.md` mục 4).
- Cảnh sẽ có chữ nhãn/headline chồng lên: luôn ghi `large empty area near the top/bottom` (đã có sẵn
  trong khối phong cách mục 2, nhắc lại nếu layout cảnh cụ thể cần chừa chỗ khác, vd giữa khung).

### Ví dụ (pilot Inuit — xem `TEMPLATE.md` mục 5 để biết preset từng cảnh dùng ảnh nào)

1. **S01 — thợ săn trên băng biển**: `An Inuit hunter kneeling alone on vast sea ice, cutting into the
   snow with a snow knife, grey overcast sky, cold blue-grey and white palette, isolated and small in
   the frame (rule-of-thirds, lots of empty space around him).` + khối phong cách
2. **S02 — cắt khối tuyết (cận cảnh)**: `Close-up of two mittened hands cutting a rectangular block of
   packed snow with a long knife, blurred figure behind, blue-grey palette.` + khối phong cách
3. **S03 — mái vòm igloo đang dựng**: `A half-built snow dome shelter on sea ice at dusk, dark sky above
   leaving empty space for a headline, blue-grey-white palette.` + khối phong cách
4. **S06 — hé lộ bên trong khối tuyết** (1 ảnh duy nhất, dùng với `PhotoKenBurns` để zoom dần, **không
   phải `SplitComparison` 2 ảnh** — xem `TEMPLATE.md` mục 3 beat 9b): `A single rectangular block of
   packed white snow, one corner just starting to peel back revealing a hint of small irregular
   ice-crystal shapes with tiny empty pockets between them, blue-white palette, flat vector diagram
   style, plain background.` + khối phong cách — ảnh **tĩnh**, cảm giác "sắp hé lộ" đến từ việc
   `PhotoKenBurns` zoom chậm vào đúng góc đã "bóc" trong ảnh, không phải animation mở dần thật

Bản đồ S04 ("Canada's Central Arctic") **không áp dụng mục này** — `MapZoom` cần ảnh bản đồ thật (địa lý
chính xác), không phải minh hoạ flat-vector; xem `RULES.md`/`HANDOFF.md` mục 7 về việc `MapZoom` không tự
có dữ liệu địa lý.

## 5. Quy trình CSV (không gọi API — giống mọi template khác trong repo)

1. Trong app: tab **Ảnh → Tính danh sách ảnh cần tạo → Tải CSV prompt**.
2. Prompt tự sinh chỉ lấy câu đầu lời dẫn + dòng phong cách chung → **thay bằng prompt viết tay theo mục 4**
   (sửa ở tab Storyboard, ô "Mô tả hình ảnh / prompt").
3. Tạo ảnh ở ChatGPT/công cụ của bạn; đặt tên file bắt đầu bằng mã cảnh (`S001_hunter.png`), 16:9.
4. Tab Ảnh → Nhập thư mục → xem từng ảnh → duyệt/từ chối.
   - Soát riêng: ảnh có bị AI tự thêm bóng đổ/gradient không (lỗi hay gặp nhất với yêu cầu flat-vector) —
     loại ngay nếu có, gen lại với câu nhấn mạnh "no gradient, no shading" rõ hơn.
5. Ghi nhãn "Minh họa AI" giống mọi tập khác (dòng chữ `caption`, chưa tự động).

## 6. Lỗi hay gặp (soát khi duyệt)

AI tự thêm bóng đổ/gradient dù đã cấm · nhân vật lệch tỉ lệ đầu-thân giữa các ảnh cùng tập (mất nhất
quán house style) · quên chừa khoảng trống cho chữ (chữ đè lên chi tiết quan trọng) · ảnh S06b trông như
ảnh chụp thật thay vì diagram (phải rõ ràng là minh hoạ, không giả vờ chính xác khoa học tuyệt đối).
