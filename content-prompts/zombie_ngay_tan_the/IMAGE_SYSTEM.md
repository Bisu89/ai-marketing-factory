# NGÀY TÀN — Hệ thống ảnh tái sử dụng (toàn bộ prompt bằng tiếng Việt)

Nguyên tắc: **không viết prompt mới từ đầu cho mỗi cảnh.** Mỗi ảnh = ghép các **khối (block)** cố định:

```
[KHỐI PHONG CÁCH] + [KHỐI NHÂN VẬT (khoá nhận diện)] + [KHỐI TRANG PHỤC/TRẠNG THÁI] + [KHỐI TƯ THẾ/HÀNH ĐỘNG] + [KHỐI BỐI CẢNH] + [KHỐI PHỦ ĐỊNH]
```

Copy **nguyên văn** từng khối — không diễn đạt lại, không "cải tiến" giữa các tập (để mặt/trang phục không trôi).
Workflow tạo ảnh: (1) tạo **bảng nhân vật** trước, (2) tạo **bảng zombie**, (3) tạo **phông nền trống** (không người), (4) với mỗi tập chỉ cần tạo thêm các **cảnh ghép** hiếm.

> Ghi chú: nếu công cụ ảnh làm mặt nhân vật trôi, đính kèm ảnh bảng nhân vật đã tạo làm tham chiếu và thêm câu: *"Giữ đúng khuôn mặt, kiểu tóc và trang phục như ảnh tham chiếu."*

---

## A. KHỐI PHONG CÁCH (dùng cho MỌI ảnh)

**[PHONG_CÁCH]**
```
Phong cách webtoon/manhwa Hàn Quốc, nét mực đen đậm sạch sẽ, tô màu phẳng 2D kiểu cel-shading, bóng đổ cứng cạnh, màu sắc rực rỡ bão hoà, bố cục điện ảnh. Tuyệt đối KHÔNG phong cách vẽ sơn dầu, KHÔNG anime bán thực, KHÔNG ảnh chụp thực tế, KHÔNG 3D render. Máu luôn là chất lỏng đen sẫm loãng (ichor), không bao giờ màu đỏ.
```

**[TỶ_LỆ_DÀI]** → `Tỷ lệ khung hình 16:9 ngang.`
**[TỶ_LỆ_NGẮN]** → `Tỷ lệ khung hình 9:16 dọc.`

**[PHỦ_ĐỊNH_CHUNG]** (đặt cuối mọi prompt)
```
PHỦ ĐỊNH: giải phẫu sai, thừa/thiếu ngón tay, mặt biến dạng, khoả thân, lộ ngực hoặc vùng nhạy cảm, tư thế gợi dục, phong cách sơn dầu, ảnh thực, anime bán thực, 3D, máu đỏ tươi, chữ, logo, watermark, ký hiệu lạ.
```

**[PHỦ_ĐỊNH_NGƯỜI_LỚN]** (dùng khi cảnh chỉ có người lớn)
```
PHỦ ĐỊNH BỔ SUNG: trẻ em, thiếu niên, nhân vật trông trẻ con.
```
Dùng **[PHỦ_ĐỊNH_CHUNG] + [PHỦ_ĐỊNH_NGƯỜI_LỚN]** cho mọi cảnh trong series này (toàn bộ nhóm chính đều là người trưởng thành).

**[CAMERA]** — chọn 1 dòng khi cần: `Cận mặt (close-up)` · `Bán thân (medium shot)` · `Toàn thân (full body)` · `Cảnh rộng (wide shot)` · `Góc thấp nhìn lên (low angle)` · `Góc cao nhìn xuống (high angle)` · `Qua vai (over-the-shoulder)`.

---

## B. KHOÁ NHẬN DIỆN NHÂN VẬT (copy nguyên văn)

### B1. [TAEHO]
```
Kang Taeho, nam 32 tuổi, cao 1m87, vai rộng, thân hình săn chắc gọn gàng. Tóc đen ngắn kiểu undercut hơi rối. Mắt nâu đen, ánh nhìn sắc lạnh. Một vết sẹo ngắn cắt qua lông mày trái, râu lún phún quanh cằm. Dây thẻ quân nhân đeo ở cổ.
```
- **[TAEHO_ĐỒ_1 – lúc đầu]:** `Áo thun đen bó sát, áo khoác dã chiến xanh ô-liu, quần túi hộp tối màu, ủng chiến đấu đen, găng hở ngón màu đen, balo quân dụng nhỏ trên lưng. Cầm dao găm chiến đấu.`
- **[TAEHO_ĐỒ_2 – sau chiến đấu]:** `Giống trang phục ban đầu nhưng áo khoác rách tay trái, áo thun dính ichor đen sẫm, vài vết xước trên cánh tay, vẻ mặt mệt mỏi.`
- **[TAEHO_QUÂN_PHỤC – hồi tưởng]:** `Quân phục dã chiến thẳng thớm kèm quân hàm thượng sĩ trên vai, mũ nồi đen, tư thế đứng nghiêm.`

### B2. [JIWOO]
```
Seo Jiwoo, nữ 29 tuổi, cao 1m68, thân hình đồng hồ cát đầy đặn. Tóc nâu đậm gợn sóng dài, buộc đuôi ngựa thấp lỏng lẻo, vài sợi tóc rơi bên má. Gọng kính mảnh đẩy lên đầu. Mắt tròn hiền. Một nốt ruồi nhỏ dưới mắt trái.
```
- **[JIWOO_ĐỒ_1 – lúc đầu]:** `Áo sơ mi trắng kem không tay, cổ áo hơi mở, váy bút chì màu nâu ngắn có đường xẻ cao bên đùi, tất lưới mỏng, giày bệt, túi xách vải đeo vai.`
- **[JIWOO_ĐỒ_2 – sau rách]:** `Áo sơ mi trắng kem bị rách vạt dưới, được buộc nút ở eo để lộ phần eo thon (kín đáo), váy bút chì bị xé xẻ cao hơn, tất rách một bên chân, trầy xước ở đầu gối, cổ chân băng bó.`

### B3. [YERIN]
```
Han Yerin, nữ 30 tuổi, cao 1m72, dáng thon cao với đôi chân dài. Tóc đen cắt bob ngang cằm, mái lệch. Mắt mèo sắc sảo, biểu cảm lạnh lùng. Một nốt ruồi nhỏ dưới khoé môi bên phải. Ống nghe đeo quanh cổ.
```
- **[YERIN_ĐỒ_1]:** `Áo scrub y tế xanh navy cổ V không tay, đã bị cắt ngắn và buộc nút vạt phía trước, áo blouse trắng khoác ngoài bị xé mất cả hai tay áo, quần lửng túi hộp màu xám, túi y tế đeo bên đùi.`
- **[YERIN_ĐỒ_2 – sau chiến đấu]:** `Giống trang phục ban đầu nhưng blouse dính ichor đen sẫm, vài vết xước trên vai, găng tay y tế dính ichor.`

### B4. [AREUM]
```
Seo Areum, nữ 26 tuổi, cao 1m75, thể hình vận động viên cân đối, đôi chân dài săn chắc. Tóc nâu tro rất dài bện thành một bím dài buông sau lưng. Mắt hổ phách quyết đoán, biểu cảm tự tin hơi bướng.
```
- **[AREUM_ĐỒ_1]:** `Áo crop thể thao đen ôm sát, bảo hộ cẳng tay trái màu đen có viền đỏ cam, găng ngón bắn cung, quần short thể thao đen, bó chân dài tới đùi, túi đựng tên đeo chéo sau lưng, cầm một cây cung thể thao.`
- **[AREUM_ĐỒ_2 – sau chiến đấu]:** `Giống trang phục ban đầu nhưng áo crop dính ichor đen sẫm, bó chân rách nhẹ ở đầu gối, vài vết xước trên bắp tay, túi tên còn ít mũi.`

### B5. [MINSEO]
```
Lee Minseo, nữ 33 tuổi, cao 1m65, nhỏ nhắn nhưng đường cong rõ. Tóc bob ngắn màu đen nhuốm tím, hơi rối. Kính tròn gọng đen với một bên tròng bị nứt. Quầng thâm dưới mắt, vẻ mặt mệt mỏi và cảnh giác. Thẻ nhân viên phòng thí nghiệm đeo ở cổ.
```
- **[MINSEO_ĐỒ_1]:** `Áo blouse phòng thí nghiệm màu trắng mở khoác ngoài áo ba lỗ trắng, quần short denim, giày thể thao, một hộp kim loại nhỏ đựng mẫu đeo chéo vai.`
- **[MINSEO_ĐỒ_2 – bẩn]:** `Giống trang phục ban đầu nhưng blouse bẩn và rách vạt, trầy xước ở cẳng tay, bụi bẩn trên má.`

### B6. Phản diện / phụ
- **[CHOI]:** `Đại tá Choi Gangsik, nam 50 tuổi, tóc muối tiêu cắt cua, gương mặt vuông nghiêm nghị, ánh mắt tính toán, quân phục xanh đậm chỉnh tề với huy hiệu đại tá, găng tay da đen.`
- **[DAHEE]:** `Baek Dahee, nữ 30 tuổi, tóc đen dài thẳng, trang điểm tinh tế, áo vest công sở màu be và chân váy ôm, vẻ mặt vừa lo lắng vừa cảnh giác.`

---

## C. KHOÁ NHẬN DIỆN ZOMBIE (copy nguyên văn)

Tất cả zombie: da xám nhợt, mắt đục trắng, máu = ichor đen sẫm loãng, quần áo rách bẩn.

**[Z_LANGTHANG – Walker]**
```
Một zombie người trưởng thành đi lê bước, da xám nhợt có đường gân đen, mắt trắng đục, miệng hơi há, quần áo thường ngày rách bẩn, tư thế gù, hai tay buông thõng. Ichor đen sẫm loãng nhỏ giọt từ vết thương.
```
**[Z_THECUONG – Runner]**
```
Một zombie đang lao chạy với tư thế thân người chúi về trước, tứ chi co giật, da xám nhợt gân đen nổi rõ, mắt trắng đục, miệng há rộng hung dữ, quần áo rách bươm. Ichor đen sẫm loãng bắn ra khi chạy.
```
**[Z_KEHU – Screamer]**
```
Một zombie gầy gò cao lêu nghêu, hàm mở quá khổ, cổ họng sưng phồng biến dạng, da xám nhợt, mắt trắng đục, đang ngửa đầu hú, ichor đen sẫm loãng chảy từ khoé miệng.
```
**[Z_THEPHINH – Bloater]**
```
Một zombie khổng lồ cao hơn 2m, bụng phình căng đầy ichor đen sẫm, da xám tím có tĩnh mạch đen nổi chằng chịt, tay ngắn so với thân, bước đi nặng nề, mắt trắng đục nhỏ.
```
**[Z_KESANMOI – Stalker]**
```
Một zombie dáng người cân đối còn nguyên vẹn, quần áo gần như sạch, da xám nhạt không có vết thương, đứng bất động hoàn toàn, đôi mắt đục trắng nhìn thẳng không chớp, biểu cảm hoàn toàn trống rỗng, đứng giữa bóng tối.
```
**[Z_THEGIAP – Aegis Soldier]**
```
Một người lính cường hoá thành zombie, thân hình cơ bắp phình to quá khổ, da xám chai cứng như giáp, đường gân đen nổi khắp người, mắt trắng đục, mũ trận đã tháo để lộ mặt xám, trang phục quân đội rách tả tơi, hai nắm đấm to quá khổ.
```

### C2. Khoá nhận diện thêm (đã được chốt cùng bảng quái vật trong `ngay_tan_series_library.csv`)

Dùng nguyên văn các khối dưới đây cho mọi cảnh có quái vật tương ứng.

**[Z_KESANMOI_SO1 – Kẻ Săn Mồi số 1 = Subject-03]** (chỉ dùng cho con đầu tiên; các Kẻ Săn Mồi khác dùng [Z_KESANMOI])
```
Một người đàn ông trưởng thành thể hình rắn chắc mặc đồ thử nghiệm màu xám nhạt còn khá sạch, đeo một chiếc vòng nhận dạng nhựa ở cổ tay phải, da xám nhạt không có vết thương, đứng bất động hoàn toàn, đôi mắt đục trắng nhìn thẳng không chớp, biểu cảm hoàn toàn trống rỗng, đứng giữa bóng tối.
```
**[Z_KEBO – Kẻ Bò (Crawler)]** — hầm, đường ống, không gian thấp
```
Một zombie bò sát nền, hai chân đã mất từ đầu gối trở xuống với phần cụt khô đen quấn vải rách, hai cánh tay dài khoẻ chống xuống kéo thân người về phía trước, da xám nhợt gân đen, mắt trắng đục, quần áo rách bám bụi, ichor đen sẫm loãng loang thành vệt kéo trên sàn.
```
**[Z_KEBAMTRAN – Kẻ Bám Trần (Lurker)]** — phục kích trong toà nhà tối
```
Một zombie gầy với tứ chi dài bất thường, bám ngược vào trần nhà bằng các đầu ngón tay cong như móc, đầu nghiêng nhìn xuống, da xám tái xanh, mắt trắng đục, quần áo rách rưới treo thõng, ichor đen sẫm loãng nhỏ giọt từ đầu ngón tay.
```
**[Z_CHONHIEM – Chó Nhiễm (Hound)]** — chạy theo bầy, đuổi nhanh ngoài đường
```
Một con chó lớn bị nhiễm, lông rụng từng mảng để lộ da xám nhợt có gân đen, xương sườn nhô lên, mắt trắng đục, hàm há để lộ răng, thân chúi thấp sẵn sàng lao tới, ichor đen sẫm loãng nhỏ giọt từ miệng.
```
**[Z_KENOHOA – Kẻ Nở Hoa (Spore Carrier)]** — giai đoạn sau, không gian kín
```
Một zombie người trưởng thành có từng mảng bào tử xám nâu như nấm mọc trên vai, lưng và cổ, vài túi bào tử phồng lên phát ra bụi mờ, da xám nhợt, mắt trắng đục, đứng chùng vai, ichor đen sẫm loãng rỉ từ các túi bào tử.
```
**[Z_BIENTHE – Walker biến thể trang phục]** — dùng để đổi cảnh (bệnh viện, văn phòng, công trường) mà vẫn là Kẻ Lang Thang
```
Sáu zombie Walker người trưởng thành đứng thành hàng, mỗi người mặc một trang phục khác nhau: bác sĩ với áo blouse rách, y tá với đồng phục nhạt màu, nhân viên văn phòng với áo sơ mi và cà vạt xộc xệch, công nhân với áo bảo hộ, nhân viên giao hàng với áo khoác và túi đeo, lính cấp dưới với quân phục rách; tất cả da xám nhợt có đường gân đen, mắt trắng đục, miệng hơi há, tư thế gù, hai tay buông thõng, ichor đen sẫm loãng nhỏ giọt từ vết thương.
```

> Quy tắc chung mọi quái vật: da xám nhợt, mắt trắng đục, máu/ichor là chất lỏng đen sẫm loãng, **không** máu đỏ, **không** nội tạng, **không** chi tiết xác chết. Quái vật là người trưởng thành hoặc động vật; không bao giờ vẽ quái vật có hình dạng trẻ em.

---

## D. KHỐI BỐI CẢNH (phông nền trống — tạo MỘT LẦN, tái dùng nhiều lần)

Mỗi phông tạo ở 2 phiên bản: **16:9** (video dài) và **9:16** (short). Không có người/zombie trong ảnh phông. Thêm hậu tố `[BỐI_CẢNH_TRỐNG]` = `Không có người, không có zombie, ảnh phông nền trống.`

| Mã | Bối cảnh | Prompt |
|---|---|---|
| **BG-01** | Đường vành đai ban đêm | `Đường cao tốc vành đai ngoại ô ban đêm, vài chiếc xe bỏ hoang, đèn đường vàng cam hắt xuống, núi xa phía sau, sương mỏng.` |
| **BG-02** | Cầu sông Hanyeon kẹt xe | `Cây cầu bắc qua sông ban đêm, hàng nghìn xe kẹt cứng, cửa mở, đèn pha còn sáng, ánh trăng phản chiếu mặt sông.` |
| **BG-03** | Hành lang trường học tối | `Hành lang trường trung học ban đêm, đèn huỳnh quang chập chờn, tủ khoá mở, giấy rơi vãi, bảng thông báo xô lệch.` |
| **BG-04** | Phòng giáo viên | `Phòng nghỉ giáo viên trường học ban đêm, bàn làm việc lộn xộn, tập bài kiểm tra, một ly cà phê còn bốc khói, ánh đèn bàn vàng.` |
| **BG-05** | ER bệnh viện | `Khoa cấp cứu bệnh viện bị tàn phá, giường bệnh đổ, đèn đỏ báo động nhấp nháy, vệt ichor đen trên sàn, cửa kính vỡ.` |
| **BG-06** | Sân thượng bệnh viện | `Sân thượng bệnh viện lúc nửa đêm, bãi đáp trực thăng, thành phố cháy âm ỉ ở xa, khói đen bay lên trời, gió mạnh.` |
| **BG-07** | Trung tâm thương mại | `Trung tâm thương mại nhiều tầng bị bỏ hoang, kệ hàng đổ, biển hiệu neon chập chờn, cầu thang cuốn ngừng hoạt động.` |
| **BG-08** | Hầm gửi xe | `Hầm gửi xe ngầm tối đen, trụ bê tông, đèn khẩn cấp đỏ, vài chiếc xe bị bỏ lại, ống nước nhỏ giọt.` |
| **BG-09** | Trung tâm bắn cung | `Sân tập bắn cung quốc gia ban đêm, bia tròn đủ màu, mái nhà vòm, đèn pha sân tập, hàng rào lưới.` |
| **BG-10** | Ngã tư đổ nát | `Ngã tư giữa phố ban đêm, đèn giao thông tắt, xe đổ nghiêng, ô tô cứu thương bị bỏ lại, hơi nước bốc lên từ cống.` |
| **BG-11** | Tiệm tạp hoá | `Cửa hàng tạp hoá nhỏ lúc rạng sáng, kệ hàng nửa trống, ánh sáng xanh lam lọt qua cửa kính, vài đồ hộp còn lại.` |
| **BG-12** | Ga tàu điện ngầm Euljiro | `Sảnh ga tàu điện ngầm bị bỏ hoang, đèn khẩn cấp xanh nhấp nháy, cửa soát vé gãy, sàn gạch ẩm ướt, đường ray tối đen ở phía dưới.` |
| **BG-13** | Đường hầm tàu điện | `Đường hầm tàu điện ngầm tối đen, ray tàu han gỉ, ống cáp treo trên trần, một ngọn đèn đỏ khẩn cấp ở xa.` |
| **BG-14** | Phòng thí nghiệm Cheonma | `Phòng thí nghiệm ngầm hiện đại, buồng kính chứa bị vỡ, đèn báo động đỏ, ống nghiệm đổ vỡ, ichor đen trên sàn.` |
| **BG-15** | Hầm dịch vụ viện | `Hầm dịch vụ bê tông chật hẹp, đường ống chạy dọc, đèn khẩn cấp vàng, cửa sắt nặng nề hé mở.` |
| **BG-16** | Nhà Dahee (đêm) | `Mặt tiền khu căn hộ cao cấp ban đêm, đèn cổng ấm, một chiếc xe quân đội đen đậu bên đường, mưa phùn.` |
| **BG-17** | Cổng viện Cheonma (ngày) | `Cổng chính khu quân sự Cheonma ban ngày, hàng rào thép gai, trạm gác, núi xanh phía sau, bầu trời xám.` |
| **BG-18** | Văn phòng Choi | `Văn phòng chỉ huy quân đội, bàn gỗ lớn, bản đồ quân sự trên tường, cờ quốc gia, rèm cửa tối.` |

---

## E. KHỐI TƯ THẾ / HÀNH ĐỘNG (tái dùng cho mọi nhân vật)

Ghép sau [KHỐI NHÂN VẬT] + [TRANG PHỤC]. Chọn 1 mã:

| Mã | Tư thế |
|---|---|
| **P-ĐỨNG** | `Đứng thẳng tư thế tự nhiên, hai tay thả lỏng, nhìn thẳng về phía trước.` |
| **P-CẢNH_GIÁC** | `Khom nhẹ người, mắt quét xung quanh, tay nắm chặt vũ khí, tư thế sẵn sàng.` |
| **P-CHẠY** | `Đang chạy hết tốc lực, tóc và quần áo bay theo gió, vẻ mặt căng thẳng.` |
| **P-CHIẾN_ĐẤU_CẬN** | `Tư thế cận chiến, một chân bước chéo về phía trước, tay cầm vũ khí giơ cao, ánh mắt quyết liệt.` |
| **P-GIƯƠNG_CUNG** | `Giương cung hết cỡ, mắt nheo ngắm mục tiêu, một chân bước trước, cánh tay vững như đá.` |
| **P-CHỮA_THƯƠNG** | `Quỳ gối xuống, hai tay đang băng bó vết thương, tập trung hoàn toàn.` |
| **P-NGHIÊN_CỨU** | `Cúi người xem ống mẫu dưới ánh đèn, kính phản chiếu ánh sáng xanh.` |
| **P-TRÁNH_NÉ** | `Né người sang bên trong tích tắc, tóc bay, một tay chống xuống đất.` |
| **P-GIẬT_MÌNH** | `Mắt mở to, người chững lại, một tay đưa lên che miệng, hoảng hốt.` |
| **P-NGHỈ_NGƠI** | `Ngồi tựa tường, kiệt sức nhưng cảnh giác, đầu hơi ngả về sau.` |
| **P-GIẬN_DỮ** | `Nghiến răng, ánh mắt giận dữ, nắm tay siết chặt.` |
| **P-NHÓM_ĐỨNG** | `Cả nhóm đứng cạnh nhau nhìn về phía trước, ánh sáng từ phía sau tạo bóng ngược.` |

**Biểu cảm khuôn mặt (ghép khi cần):** `bình thản` · `lo lắng` · `sợ hãi` · `giận dữ` · `kiệt sức` · `quyết tâm` · `bất ngờ` · `đau lòng`.

---

## F. CÔNG THỨC GHÉP MẪU

### F1. Ảnh nhân vật đơn
```
[PHONG_CÁCH] + [TỶ_LỆ] + [NHÂN VẬT] + [TRANG PHỤC] + [TƯ THẾ] + [BỐI CẢNH] + [PHỦ_ĐỊNH_CHUNG] + [PHỦ_ĐỊNH_NGƯỜI_LỚN]
```
**Ví dụ hoàn chỉnh (Areum giương cung, 16:9):**
```
Phong cách webtoon/manhwa Hàn Quốc, nét mực đen đậm sạch sẽ, tô màu phẳng 2D kiểu cel-shading, bóng đổ cứng cạnh, màu sắc rực rỡ bão hoà, bố cục điện ảnh. Tuyệt đối KHÔNG phong cách vẽ sơn dầu, KHÔNG anime bán thực, KHÔNG ảnh chụp thực tế, KHÔNG 3D render. Máu luôn là chất lỏng đen sẫm loãng (ichor), không bao giờ màu đỏ. Tỷ lệ khung hình 16:9 ngang. Seo Areum, nữ 26 tuổi, cao 1m75, thể hình vận động viên cân đối, đôi chân dài săn chắc. Tóc nâu tro rất dài bện thành một bím dài buông sau lưng. Mắt hổ phách quyết đoán, biểu cảm tự tin hơi bướng. Áo crop thể thao đen ôm sát, bảo hộ cẳng tay trái màu đen có viền đỏ cam, găng ngón bắn cung, quần short thể thao đen, bó chân dài tới đùi, túi đựng tên đeo chéo sau lưng, cầm một cây cung thể thao. Giương cung hết cỡ, mắt nheo ngắm mục tiêu, một chân bước trước, cánh tay vững như đá. Đứng trên mái nhà vòm của sân tập bắn cung quốc gia ban đêm, đèn pha sân tập phía sau tạo ánh sáng ngược, vài zombie nhỏ ở xa bên dưới. PHỦ ĐỊNH: giải phẫu sai, thừa/thiếu ngón tay, mặt biến dạng, khoả thân, lộ ngực hoặc vùng nhạy cảm, tư thế gợi dục, phong cách sơn dầu, ảnh thực, anime bán thực, 3D, máu đỏ tươi, chữ, logo, watermark, ký hiệu lạ. PHỦ ĐỊNH BỔ SUNG: trẻ em, thiếu niên, nhân vật trông trẻ con.
```

### F2. Ảnh nhóm
Ghép: `[PHONG_CÁCH] + [TỶ_LỆ] + "Năm người đứng cạnh nhau từ trái sang phải:" + [TAEHO]+[ĐỒ] ; [JIWOO]+[ĐỒ] ; [YERIN]+[ĐỒ] ; [AREUM]+[ĐỒ] ; [MINSEO]+[ĐỒ] + [P-NHÓM_ĐỨNG] + [BỐI CẢNH] + [PHỦ_ĐỊNH]`.
Ảnh nhóm khó giữ nhất quán — nên tạo **mỗi nhân vật riêng rồi ghép trong khâu dựng video** nếu AI làm sai mặt.

### F3. Cảnh nhân vật đối mặt zombie
```
[PHONG_CÁCH] + [TỶ_LỆ] + [NHÂN VẬT] + [TRANG PHỤC] + [P-CHIẾN_ĐẤU_CẬN] + "Đối diện với" + [Z_xxx] + [BỐI CẢNH] + [PHỦ_ĐỊNH]
```

---

## G. DANH SÁCH ẢNH CẦN TẠO TRƯỚC (thư viện nền — làm 1 lần)

### G1. Bảng nhân vật (5 ảnh, ưu tiên cao nhất)
Mỗi ảnh = nhân vật đứng toàn thân, chính diện, phông trắng, `[ĐỒ_1]`. Prompt:
```
[PHONG_CÁCH] Bảng thiết kế nhân vật: [KHỐI NHÂN VẬT] + [ĐỒ_1], đứng thẳng toàn thân nhìn thẳng, phông nền trắng trơn, ba góc nhìn (chính diện, nghiêng, sau lưng) xếp cạnh nhau. [PHỦ_ĐỊNH_CHUNG] + [PHỦ_ĐỊNH_NGƯỜI_LỚN]
```
→ **CS-TAEHO, CS-JIWOO, CS-YERIN, CS-AREUM, CS-MINSEO** (+ **CS-CHOI**, **CS-DAHEE** nếu cần).

### G2. Bảng biểu cảm (5 ảnh)
```
[PHONG_CÁCH] Bảng biểu cảm của [KHỐI NHÂN VẬT]: 8 khuôn mặt cận cảnh xếp lưới 4x2 với các biểu cảm: bình thản, lo lắng, sợ hãi, giận dữ, kiệt sức, quyết tâm, bất ngờ, đau lòng. Phông trắng. [PHỦ_ĐỊNH_CHUNG] + [PHỦ_ĐỊNH_NGƯỜI_LỚN]
```

### G3. Bảng trạng thái trang phục (10 ảnh)
Mỗi nhân vật 2 ảnh: `ĐỒ_1 (sạch)` và `ĐỒ_2 (rách/bẩn)` — toàn thân chính diện, phông trắng.

### G4. Bảng zombie (6 ảnh)
Mỗi loại 1 ảnh toàn thân, nhiều tư thế (đứng, tấn công, ngã) xếp 3 cột, phông trắng — dùng đúng khối `[Z_xxx]`.

### G5. Phông nền trống (18 × 2 tỷ lệ = 36 ảnh)
Dùng bảng D. Ưu tiên cho Tập 1–4: **BG-01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18** (tất cả đều dùng trong 4 tập đầu).

### G6. Ảnh cảnh hiếm (làm riêng mỗi tập, ≈8–12 ảnh/tập)
Danh sách sơ bộ cho 4 tập đầu:

**TẬP 1**
1. Taeho nghiêm trang trong quân phục, chứng kiến thử nghiệm (BG-17 + [TAEHO_QUÂN_PHỤC]).
2. Minseo khóc sau tấm kính phòng thí nghiệm, Taeho đi ngang (BG-14).
3. Minseo nhét thẻ nhớ vào tay Taeho (cận cảnh hai bàn tay).
4. Đại tá Choi đưa quyết định kỷ luật cho Taeho (BG-18).
5. Taeho bước tới nhà Dahee, mưa phùn (BG-16).
6. Dahee bước xuống xe quân đội, Taeho nấp nhìn.
7. Taeho thả chiếc nhẫn xuống rãnh nước (cận cảnh).
8. Subject-03 phá vỡ kính (BG-14 + Z_THECUONG).
9. Minseo chạy vào hầm dịch vụ với hộp mẫu (BG-15).
10. Taeho dừng xe ở vành đai, zombie đập kính xe (BG-01 + Z_LANGTHANG).

**TẬP 2**
1. Taeho dẫn Walker đi bằng tiếng ồn trên cầu (BG-02).
2. Jiwoo chặn cửa phòng văn thư bằng cặp táp (BG-04).
3. Runner lao vào Jiwoo, Taeho cứu (BG-03).
4. Yerin ở ER lệnh cách ly bệnh nhân (BG-05).
5. Yerin gọi điện cho Minseo — máy bận.
6. Taeho + Jiwoo đi men tường trong trung tâm thương mại đầy Walker (BG-07).
7. Jiwoo chỉ lối tắt qua hầm xe (BG-08).
8. Areum giương cung trên mái nhìn xuống (BG-09).
9. Close-up mũi tên rời dây cung.

**TẬP 3**
1. Mũi tên găm Runner sau lưng Taeho.
2. Areum nhảy từ mái xuống.
3. Jiwoo bị thương cổ chân.
4. Screamer hú ở ngã tư (BG-10 + Z_KEHU) + đàn zombie đổ về.
5. Taeho lái xe tải húc rào chắn.
6. Yerin trên sân thượng với bốn bệnh nhân (BG-06).
7. Bloater ở hành lang tầng 4, Taeho dụ nó.
8. Areum bắn nổ Bloater, ichor bắn tung toé.
9. Bệnh nhân bị cắn chuyển hoá trong cầu thang.
10. Yerin đọc tin nhắn từ Minseo.
11. Trực thăng quân sự lướt qua bầu trời đêm.

**TẬP 4**
1. Cảnh nghỉ ngơi trong tiệm tạp hoá (BG-11): Jiwoo viết nhật ký, Areum mài tên, Yerin băng chân.
2. Cả nhóm đi men đường ray trong hầm (BG-13).
3. Minseo chĩa ống tiêm từ bóng tối (BG-12).
4. Yerin ôm Minseo (cảm xúc).
5. Taeho đưa vỏ thẻ quân nhân chứa thẻ nhớ ra, hai người nhìn nhau.
6. Loa phóng thanh quân đội trên sảnh ga.
7. Choi + Dahee + đội lính xuất hiện ở cửa ga.
8. Dahee nhìn Taeho sửng sốt.
9. Thể Giáp tháo mũ (Z_THEGIAP).
10. Thể Giáp lao vào nhóm.
11. Nhóm phối hợp: Areum bắn, Taeho đâm, Yerin kéo Minseo, Jiwoo bật đèn.
12. Trần hầm sập xuống.
13. Kẻ Săn Mồi đứng im trong bóng tối (BG-13 + Z_KESANMOI).

---

## H. QUY TRÌNH ĐẶT TÊN FILE ẢNH

```
content-prompts/zombie_ngay_tan_the/images/
  characters/   CS-TAEHO.png ...
  expressions/  EX-TAEHO.png ...
  outfits/      OF-TAEHO-1.png, OF-TAEHO-2.png ...
  zombies/      Z-LANGTHANG.png ...
  backgrounds/  BG-01_16x9.png, BG-01_9x16.png ...
  scenes/       ep1_s01.png ...
```
Tag khi import vào Asset Library: `nhân_vật:taeho`, `bối_cảnh:bg-12`, `zombie:kesanmoi`, `tập:1`... để tìm lại nhanh khi dựng.

---

## I. MẪU BẢNG THIẾT KẾ CHUẨN (template ảnh để khoá nhân vật / quái vật)

Mọi bảng nhân vật và bảng quái vật trong series dùng **cùng một khung** để mặt, dáng, bảng màu không trôi. Các bảng đã có sẵn prompt trong `ngay_tan_ep1_scenes.csv` (nhân vật) và `ngay_tan_series_library.csv` (quái vật + poster).

**Khung chuẩn nhân vật** — một ảnh gồm: ba góc nhìn toàn thân (chính diện, nghiêng, sau lưng) trên phông trắng trơn, thấy rõ bàn tay và bàn chân; một dải năm ô màu thể hiện bảng màu nhận diện của nhân vật (xanh ô-liu + đen cho Taeho, kem + nâu cho Jiwoo, navy + trắng cho Yerin, đen + đỏ cam cho Areum, teal + trắng cho Minseo); tuyệt đối không có chữ.

**Khung chuẩn quái vật** — ba tư thế đặc trưng xếp thành ba cột, toàn thân trên phông trắng, một ô cận cảnh chi tiết nhận diện (vòng nhận dạng, bụng phình, túi bào tử...), dải năm ô màu chủ đạo; không có chữ.

**Cách dùng để khoá nhất quán**
1. Tạo bảng của từng nhân vật/quái vật một lần; chọn bản đẹp nhất, lưu đúng tên file trong CSV.
2. Khi tạo cảnh: đính kèm bảng liên quan làm ảnh tham chiếu và thêm câu: *"Giữ đúng khuôn mặt, kiểu tóc, trang phục và hình dáng như ảnh tham chiếu."*
3. Cảnh có nhiều nhân vật: tạo từng người riêng rồi ghép trong khâu dựng nếu AI làm sai mặt.
4. Bản poster tổng hợp (`poster_nam_nhan_vat_chinh.png`, `poster_tong_hop_quai_vat.png`, `bieu_do_so_sanh_kich_thuoc.png`) dùng để đối chiếu cuối cùng, không dùng làm ảnh dựng video.

**Bảng nhân vật tổng hợp (đã chốt):** một ảnh chứa cả 7 nhân vật, mỗi người có nhãn tên: KANG TAEHO (강태호), SEO JIWOO (서지우), HAN YERIN (한예린), SEO AREUM (서아름), LEE MINSEO (이민서), CHOI GANGSIK (최강식), BAEK DAHEE (백다희). Lưu với tên `bang_nhan_vat_tong_hop.png`. Prompt ảnh cảnh chỉ cần đính kèm ảnh này và gọi nhân vật đúng theo tên trong bảng (đã áp dụng cho `ngay_tan_ep1_scenes_v3.csv`); chỉ mô tả thêm khi trang phục thay đổi hoặc rách/bẩn. Quái vật dùng bảng zombie riêng.
