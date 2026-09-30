# Đại Quản Gia Là Ma Hoàng

- **Nguồn:** https://manhuavn2.com/dai-quan-gia-la-ma-hoang-0.html
  (hạng #1 top tháng, 70K lượt/tháng tại 2026-09-28; tác giả Trác Nhất Phàm)
- **Quy mô:** 915 chương, còn đang ra. **Chương 1–283 miễn phí**, từ 284 trở đi là VIP.
- **Nguồn thứ 2 (tải tự động được):** https://cotruyenday.com/truyen-tranh/dai-quan-gia-la-ma-hoang-6986/chapter-0
  Chương 0–10 tải thẳng bằng `recap.py fetch <link> <thư mục> --count N`. Từ chương 11 trở đi phải đăng nhập, không có ảnh.
- **Tải ảnh (manhuavn2):**
  - Chương 1–2 nằm trên `img2.truyensieuhay.com` và chương 200 trên blogspot: `recap.py fetch` tải được.
  - **Chương 3–100+ nằm trên `img02.g5img.top`, bị chặn tải (403).** Phải tải tay bằng extension trình duyệt vào `manhua-recap/dqg_epN/`, đặt tên `c03_001.jpg`…
- **Rủi ro:** trang ghi "nghiêm cấm reup", cộng thêm rủi ro reused content trên YouTube. Vì vậy mỗi tập đều có câu bình luận riêng.
- **Viết kịch bản bằng GPT ngoài (tiết kiệm token Claude):** xem [`GPT_SCRIPT_PROMPT.md`](GPT_SCRIPT_PROMPT.md) --
  prompt dán sẵn để GPT đọc link chương và viết kịch bản; Claude chỉ khớp panel + build + render.

## Tiền đề (đã đọc chương 1–2)

Ma Hoàng **Trác Nhất Phàm**, thủ lĩnh Bát Hoàng của Thánh Vực, có được **Cửu U Mật Lục** (di vật của Ma Đế).
Chính đạo và Thánh Vực vây Thiên Ma Phong. Hắn bị chính đệ tử ruột **Triệu Thành** đâm lén từ sau lưng, vì hắn không cho Triệu Thành xem bí kíp.
Trác Nhất Phàm tự bạo để hủy bí kíp. Linh hồn rơi xuống nhân giới, nhập vào **Trác Phàm**, một thiếu niên gia nô của **Lạc gia**.

Cha của Trác Phàm đã chết để bảo vệ Lạc gia. Cậu bé thề báo ơn, nhưng chết trước khi kịp làm, nên chấp niệm hóa thành **tâm ma**.
Hệ quả: **Ma Hoàng cứ rời xa Lạc gia là tim đau như xé**, nên buộc phải làm "nô tài" bảo vệ Lạc gia. Đây là nghịch lý chính của truyện.

**Nhân vật:**

| Tên | Vai trò |
|---|---|
| Trác Nhất Phàm / Trác Phàm | Nhân vật chính, Ma Hoàng trong thân xác thiếu niên |
| Triệu Thành | Đệ tử phản bội, mục tiêu báo thù |
| Kiếm Hoàng | Kẻ thù ở Thánh Vực |
| Lạc Vân Thường (đại tiểu thư Lạc gia) và em trai (thiếu gia) | Những người hắn phải bảo vệ |
| Bàng Diên | Thống lĩnh hộ vệ Lạc gia, người trung thành |
| Tôn Triết | Quản gia Lạc gia, kẻ phản bội, cấu kết sơn tặc để cướp Hồi Long Chưởng |

Tên tiểu thư Lạc Vân Thường là tên theo truyện gốc, chưa thấy xuất hiện trong chương 1–2. Cần xác nhận khi đọc các chương sau.

## Công thức kênh (theo NBToon, xem docs/features/153)

- Mở bằng "X này + nghịch lý".
- Quay về quá khứ bằng "Chuyện bắt đầu…".
- Kết lửng.
- Có 2–4 câu bình luận (giọng nữ). Phụ đề một chữ màu ngẫu nhiên. Khung giữ nguyên trên nền mờ.

## Kế hoạch tập

| Tập | Chương | Thư mục ảnh | Tiêu đề | Trạng thái |
|---|---|---|---|---|
| 1 | 1 | `manhua-recap/dqg_ep1` | Ma Hoàng bị chính đệ tử phản bội!? | ✅ script (Claude viết) |
| 2 | 2 | `manhua-recap/dqg_ep2` | Ma Hoàng bị trói vào... một tiểu thư!? | ✅ script (Claude viết) |
| 3 | 3–6 | `manhua-recap/dqg_ep3` | *(Ma Hoàng đi làm quản gia!?)* | ⏳ đã tải từ cotruyenday (418 khung), chờ Claude đọc + viết |
| 11 | 11 | `manhua-recap/dqg_ep11` | Ma Hoàng thắng Ma Đạo, nhưng kẻ thù thật sự mới vừa xuất hiện!? | ✅ project 124 / job_183, Final QA PASS 100 (51.44s, 1080×1920) |
| 11 (KR) | 11 | `manhua-recap/dqg_ep11` | 마황, 마도 고수를 이겼지만 진짜 적은 이제 막 나타났다!? | ✅ project 125 / job_184, Final QA PASS 100 (71.0s, 1080×1920) |
| 12 | 12 | `manhua-recap/dqg_ep12` | Ma Hoàng liều mạng luyện công, đánh thức quỷ dữ trong chính mình!? | ✅ project 128 / job_187, Final QA PASS 100 (50.04s, 1080×1920) |
| 13 | 13 | `manhua-recap/dqg_ep13` | Quái vật tàn sát Thái phủ, hóa ra là con ruột của chính Ma Hoàng!? | ✅ project 129 / job_188, Final QA PASS 100 (52.52s, 1080×1920) |
| 14 | 14 | `manhua-recap/dqg_ep14` | Ma Hoàng đi xin nhà, tiện tay lột trần gián điệp ẩn náu bấy lâu!? | ✅ project 132 / job_192, Final QA PASS 100 (52.65s, 1080×1920) |
| 15 | 15 | `manhua-recap/dqgl_ep15` | Ma Hoàng chỉ dọn nhà, vô tình khiến cả thiên hạ chấn động!? | ✅ project 134 / job_193, Final QA PASS 100 (47.78s, 1080×1920) |
| 16 | 16 | `manhua-recap/dqgl_ep16` | Ma Hoàng từ chối làm đại gia, lại cứu Lạc gia khỏi âm mưu bắt cóc!? | ✅ project 135 / job_194, Final QA PASS 100 (43.0s, 1080×1920) |
| 17 | 17 | `manhua-recap/dqgl_ep17` | Chưa kịp bắt cóc, thủ lĩnh Hắc Phong Sơn đã bị Ma Hoàng bắt sống!? | ✅ project 136 / job_195, Final QA PASS 100 (40.36s, 1080×1920) |
| 18 | 18 | `manhua-recap/dqgl_ep18` | Kẻ chủ mưu thật sự không phải nữ trại chủ, mà là vị hôn phu của cô!? | ✅ project 137 / job_196, Final QA PASS 100 (38.98s, 1080×1920) |
| 19 | 19 | `manhua-recap/dqgl_ep19` | Dương Minh bày cả vở kịch, đến cha nuôi cũng chỉ là quân cờ!? | ✅ project 138 / job_198, Final QA PASS 100 (44.98s, 1080×1920) |
| 4–10, 20+ | theo arc | | | Chương 3–10 chỉ có bản dài (Long01); chương 11 là Short đầu tiên nối tiếp sau Long01, chưa làm Short riêng cho 3–10. Từ chương 15, thư mục ảnh đổi tên thành `dqgl_epNN` (gõ nhầm của phiên khác, không phải `dqg_epNN`) |

## Video dài

| Video | Chương | Thư mục ảnh | Tiêu đề | Trạng thái |
|---|---|---|---|---|
| Long 01 | 1–10 | `manhua-recap/dqg_long01` (cotruyenday, `fetch --count 10`) | Ma Hoàng thành quản gia \| Tóm tắt chương 1-10 | ✅ script `long01/script.json` (170 beat, 11 phần), ghi chú đọc truyện chi tiết trong `long01/notes.md` |
| Long 02 | 11–15 | tái dùng panel từ `dqg_ep11..14` + `dqgl_ep15` (không cắt lại) | Ma Hoàng thành quản gia \| Tóm tắt chương 11-15 | ✅ script `long02/script.json` (100 beat, 5 phần), project 141 / job_200, **Final QA PASS 100 (337.67s ≈ 5:38, 1920×1080)** |
| Long 03 | 16–20 | tái dùng panel từ `dqgl_ep16..20` (không cắt lại) | Ma Hoàng thành quản gia \| Tóm tắt chương 16-20 | ✅ script `long03/script.json` (74 beat, 5 phần), project 142 / job_203, **Final QA PASS 100 (270.39s ≈ 4:30, 1920×1080)** |

Nhân vật mới ở chương 3–10: **Bàng Vũ** (thống lĩnh hộ vệ), **Lạc Vân Hải** (thiếu gia), **Tôn quản gia** (đã chết ở chương 4),
thiếu trại chủ Hắc Phong Sơn (chủ mưu, muốn cướp Hồi Long Chưởng), **Thái Hiếu Đình** (vị hôn phu phản bội), gia chủ Thái gia,
**Tôn Vũ Phi** (thuộc Ngự Hạ Thất Thế Gia, thề trả thù), **Long Quỳ** và **Thần Nhãn Long Cửu** (Tiềm Long Các).
Đạo cụ quan trọng: Huyết Tinh Linh, dùng để luyện Huyết Anh bổn mạng; Thượng Cổ Trận Thức Đồ, bán giá 1000 vạn.

Nhân vật mới ở chương 11: **Tôn gia** kéo tới vây Lạc gia đòi giao nộp Trác Phàm để trả thù cho "biểu muội" (ngầm hiểu
là Tôn Vũ Phi, thuộc Ngự Hạ Thất Thế Gia). Đi cùng có một cô em họ nóng nảy (muốn diệt tộc Lạc gia ngay) và **U Tuyền**
— biểu ca của cô, đệ tử **U Minh Cốc** (môn phái Ma Đạo), dùng **Huyết Ảnh Chưởng**. Trác Phàm hạ hắn bằng **U Minh Trảo**
(đúng tuyệt kỹ của môn phái đối phương) rồi điểm tâm mạch; U Tuyền cùng đường tự bạo tâm mạch phản đòn, cả hai cùng bị
thương nặng. Chương kết lửng: một kẻ lạ mặt xuất hiện, nhắm thẳng Lạc Vân Thường — chưa rõ danh tính, để ngỏ cho tập 12.

Nhân vật mới ở chương 12: **Long Kiệt** (biệt danh "A Kiệt"), người của **Tiềm Long Các**, được chú (**Long Cửu**,
gọi là "Cửu Thúc"/"Cửu gia") phái tới bảo vệ Lạc gia — chính là "kẻ lạ mặt" kết lửng cuối tập 11, hóa ra không nhắm
vào Lạc Vân Thường mà ra tay chặn U Tuyền (dùng **Tiềm Long Trảo**). Giữa lúc hỗn loạn, Trác Phàm bộc phát toàn lực
Ma Hoàng và tự tay kết liễu U Tuyền — hóa ra là tính toán từ đầu, mượn tay Long Kiệt để đẩy **Tiềm Long Các** và
**U Minh Cốc** vào thế nghi kỵ nhau, dồn Long Cửu vào thế phải công khai bảo vệ Lạc gia để giữ thể diện (có một
nhân vật phụ "Tiểu Quỷ", cháu gái/hậu bối của Long Cửu). Trác Phàm tự nhận trận đó mình thực chất đã thua, kẻ thù
thật sự giờ là cả **Ngự Hạ Thất Thế Gia** (gia tộc của U Tuyền) — liều mạng đột phá cảnh giới một mình, phản tác
dụng, đánh thức một nhân cách/thế lực khác từ bên trong cơ thể, thề diệt tộc **Thái gia**. Kết lửng mới: mối nguy
không đến từ bên ngoài mà từ chính bên trong Trác Phàm.

Chương 13 giải thích luôn "thứ đánh thức" ở cuối tập 12: đó chính là **Huyết Anh** (bản mệnh huyết anh luyện từ
Huyết Tinh Linh, xem mục "Đạo cụ quan trọng" ở chương 1–10) — không hẳn phản tác dụng như tưởng, mà là luyện thành
công một sinh vật bán tự chủ, gắn với tâm mạch Trác Phàm (hai bên cùng sống cùng chết, nhưng Huyết Anh còn sống thì
tâm mạch tự bạo cũng không nguy hiểm tính mạng). Nó tự ý đi tàn sát **Thái phủ** (tự xưng giết người thứ 50), khiến
U Minh Cốc tưởng nhầm chính **Tiềm Long Các** giết U Tuyền (đúng ý đồ Trác Phàm gài từ tập 12) — nhân tiện phát hiện
U Minh Cốc đã cài gián điệp ngay trong Tiềm Long Các, kể cả ở **Hắc Phong Sơn** (bãi trại cũ từ arc chương 1–10).
Thái gia chủ hóa ra căm hận riêng Trác Phàm vì trước đó đã cấy tà thuật (Huyết Anh) vào con trai ông
(**Thái Hiếu Đình**, vị hôn phu phản bội cũ) để dạy bài học — nhưng không dám ra tay vì sợ liên lụy tới Tiềm Long
Các. Nhờ Huyết Anh, Trác Phàm đột phá cảnh giới nhanh gấp đôi bình thường, kết chương với thái độ tự tin, sẵn sàng
đối đầu Hắc Phong Sơn ở tập sau.

Chương 14: mở đầu nhẹ nhàng — Lạc Vân Thường đứng canh ngoài cửa phòng Trác Phàm suốt đêm vì lo hắn bị thương
(sau vụ tập 13), hắn bối rối đổ lỗi cho "tâm ma". Sau đó Bàng Diên đưa hắn tới **Tiềm Long Các** xin một chỗ ở cố
định cho Lạc gia — gặp lại **Long Qùy** (từ arc chương 1–10) vẫn còn hiềm khích, nhưng chính **Long Cửu** ra mặt
dàn xếp. Trác Phàm lật ngược thế cờ: biến việc xin nhà thành "Tiềm Long Các nợ Lạc gia", vừa được cấp biệt viện
vừa cho họ cớ chính đáng để tiếp tục giám sát/bảo vệ. Đổi lại, hắn tặng thêm tin tình báo: gián điệp U Minh Cốc
cài trong Tiềm Long Các và Hắc Phong Sơn (phát hiện từ tập 13) chính là **Giản Trưởng Lão** — hóa ra chính là kẻ
từng hủy một mắt của Long Cửu nhiều năm trước. Long Cửu nổi giận, huy động toàn bộ trưởng lão gia tộc truy sát.
Kết tập: Trác Phàm mỉm cười hài lòng — một nước cờ vừa có nhà ở, vừa có đồng minh nợ ân tình, vừa trả thù giúp
người khác mà không tốn công sức.

Chương 15: sau khi dọn vào biệt viện mới bị một quý tộc Tiềm Long Các mỉa mai "ếch ngồi đáy giếng", Trác Phàm
lặng lẽ nâng cấp trận trấn thủ có sẵn của **Long Cửu** (Bàn Long Trận) từ tam cấp lên hẳn **ngũ cấp** — trình độ mà
cả đời Long Cửu (trận sư mạnh nhất họ biết) chưa từng đạt tới, gây chấn động khắp Thiên Vũ Đế Quốc. Long Cửu đích
thân mời Trác Phàm làm "cung phụng" của Tiềm Long Các (vị trí danh dự, bỏ qua cả thân phận quản gia nhỏ bé), xưng
hô ngang hàng "lão đệ"/"Cửu ca". Kết lửng: Trác Phàm chưa trả lời.

Chương 16: Trác Phàm từ chối lời mời cung phụng — điều kiện hắn ra không phải cho bản thân mà là bảo vệ trọn đời
cho toàn bộ Lạc gia (Long Cửu đồng ý, hứa cả "đời đời tử tôn"). Tới ngày hẹn chính thức, hắn thẳng thừng từ chối
làm cung phụng, tự xưng Đại quản gia Lạc gia, tuyên bố mười năm sẽ đưa Lạc gia vượt mặt Tiềm Long Các — triết lý
Ma Đạo của hắn: "mệnh của ta do ta, không phải do trời". Song song đó, **Huyết Anh** (từ tập 13) vẫn âm thầm tàn
sát người của Thái gia không ai hay, nhưng bị một **nữ nhân bí ẩn tóc tím** phát hiện và bám theo — người này hóa
ra đang do thám cấu trúc phòng thủ của biệt viện Lạc gia, đã bắt tay với **U Minh Cốc** để dụ hộ vệ rời vị trí,
mục tiêu: xông vào giết sạch người Lạc gia, bắt sống **Lạc Vân Thường**. Kết lửng: âm mưu bị Huyết Anh tình cờ
nghe được, nhưng chưa ai trong Lạc gia hay biết.

Chương 17: danh tính "nữ nhân bí ẩn tóc tím" từ tập 16 được xác nhận: **Lôi Vũ Đình**, nghĩa nữ sơn chủ **Hắc
Phong Sơn** (bãi trại cũ từ arc chương 1–10), thề diệt trừ Lạc gia để báo thù cho cha nuôi bị thương, bắt tay
**U Minh Cốc**. Nhưng trước khi cô kịp ra tay, chính Trác Phàm đột nhập doanh trại Hắc Phong Sơn giữa đêm, để lộ
thân phận rồi dùng **Huyết Anh** khống chế cô ngay tại chỗ, bắt cả cô lẫn thuộc hạ **Tiểu Thúy** về thẩm vấn. Ép
cung (bằng chiêu hù dọa "đếm tới ba") lấy được toàn bộ kế hoạch: U Minh Cốc sẽ dụ người Tiềm Long Các rời vị trí
để Hắc Phong Sơn thừa cơ tấn công — nhưng Lôi Vũ Đình không biết đầu mối liên lạc thật sự với U Minh Cốc là ai.
Kết lửng: một cảnh hoàn toàn mới, chưa rõ nhân vật, cắt ngang bằng tiếng thét "Đừng mà!" — để ngỏ cho tập 18.

Chương 18: tiếp cảnh "Đừng mà!" — hóa ra là một cô hầu gái khác bị thẩm vấn tiếp, khai ra: toàn bộ âm mưu không do
Lôi Vũ Đình chủ mưu, mà do **Dương Minh**, vị hôn phu của cô và đệ tử thân cận của sơn chủ Hắc Phong Sơn. Chính
Dương Minh (không phải Lạc gia) đã móc nối với quản gia phản bội cũ của Lạc gia (**Tôn quản gia**, chết ở chương 4)
để lật đổ Lạc gia năm xưa — và mọi "bằng chứng" Lôi Vũ Đình tin (Lạc gia hại cha nuôi cô, Hồi Long Chưởng trị được
thương) đều chỉ do một mình Dương Minh kể lại, chưa ai kiểm chứng độc lập. Trác Phàm nghi cả Lạc gia lẫn Hắc Phong
Sơn chỉ là quân cờ của **Ngự Hạ Thất Thế Gia**, đòi Lôi Vũ Đình đích thân dẫn mình về tận Hắc Phong Sơn điều tra.
Tới nơi, phát hiện chuyến đi "tuyệt mật" của cô đã bị lộ cho lính gác biết trước — dấu hiệu Dương Minh giám sát cô
sát sao. Kết lửng: một bóng người xám bạc xuất hiện, chào thân mật "Vũ Đình muội muội" rồi ra tay tấn công ngay —
chính là **Dương Minh**.

Chương 19: Dương Minh không thật sự định giết Lôi Vũ Đình (ít nhất chưa phải lúc này) — hôm sau vẫn ân cần như
thường. Cô mời một lang y giang hồ tới chữa cho cha nuôi; Dương Minh cản trở rồi mới "cho phép" (viện cớ thử thực
lực). Không tin tưởng, cô nhờ **Trác Phàm** đích thân giả làm lang y khác tới khám — phát hiện chấn động: sơn chủ
**không hề** có ngoại thương lẫn nội thương như Dương Minh vẫn kể, nguyên nhân thật là một **dị vật nhập thể**
(gợi ý ông bị đầu độc/cấy thứ gì đó, không phải bị Lạc gia ám sát). Dương Minh lộ mặt, kích hoạt cơ quan bí mật đẩy
cả hai xuống hầm tối, thú nhận lạnh lùng: ông không hề quan tâm cha nuôi sống chết, thậm chí còn định cho ông uống
nhầm thuốc vì chẳng biết bệnh thật là gì — chỉ lo "đại kế" riêng. Bị nhốt, "lão lang y" (Trác Phàm cải trang) trấn
an mọi việc vẫn trong kế hoạch. Kết chương: ông triệu hồi **Huyết Anh**, ra lệnh lạnh lùng "đi đi, tiêu diệt bọn
chúng" — chuẩn bị phá ngục.

Hai bản cũ do OpenAI viết (project 115/116, tiêu đề khác) được giữ để so sánh. Bản chính thức là bản Claude viết.

## Khung đã xóa trước khi cắt kịch bản

Đây là các khung logo, quảng cáo QR app và credit nhóm dịch.
Ở máy mới, sau khi chạy `cut` thì xóa lại đúng các file này để tên khung khớp với `script.json`.
Việc xóa không đổi tên các khung còn lại.

- `dqg_ep1`: p001, p002, p115, p116, p117
- `dqg_ep2`: p001, p002, p071, p072, p073

## Nhật ký

- 2026-09-30: Long 02 + Long 03 (chương 11–20, tách đôi) — thay vì tải lại/cắt lại ảnh vào một thư mục gộp như
  Long01, tổng hợp trực tiếp 174 beat từ 10 kịch bản Short ep11-ep20 đã viết tay (bớt "Ma Hoàng này..." lặp lại đầu
  mỗi tập, đổi `type` HOOK/ENDING giữa các tập thành BUILD, thêm `section` mỗi tập). **`recap.py build` không hỗ
  trợ nhiều thư mục panel trong một lần build** (chỉ nhận một `chapter_dir`), nên build thủ công qua API: script
  Python tra `asset_id` theo đường dẫn panel đầy đủ của từng tập (ảnh đã được đăng ký sẵn từ lần build Short trước
  đó, không cần đăng ký lại). **Lưu ý quan trọng:** trường `section` trong `script.json` **không** phải field của
  beat-plan API (`PUT /beat-plan` trả 422 "Extra inputs are not permitted" nếu gửi kèm `section` trong object beat)
  — `recap.py`'s `cmd_build` không hề gửi `section` lên backend, nó chỉ tồn tại trong file `script.json` cục bộ để
  lệnh `timestamps` đọc lại sau khi render xong (khớp với thời điểm thật của beat).
  - **Sự cố lớn:** bản gộp nguyên 174 beat (project 140, ~11 phút) **fail 16 lần liên tiếp** ở GENERATING_VOICE
    (edge_tts "No audio was received"), thử cả hai giọng (nam `vi-VN-NamMinhNeural` và nữ `vi-VN-HoaiMyNeural`),
    luôn fail ở thời điểm khác nhau mỗi lần — không phải một đoạn "độc" cố định mà là lỗi xác suất: càng nhiều beat
    dồn vào một lần render (càng nhiều lệnh gọi edge_tts liên tiếp) càng dễ dính chuỗi lỗi ở đâu đó trên endpoint
    miễn phí của Microsoft (theo nhận định của user, có vẻ endpoint kém ổn định hơn hẳn với tiếng Việt so với các
    ngôn ngữ phổ biến). Giữa chừng phát hiện **phiên khác đang sửa đúng vấn đề edge_tts này** trong
    `backend/app/modules/voice/providers.py` (đã lưu trên đĩa nhưng backend `--reload` không tự nạp): tăng
    `_SEGMENT_MAX_ATTEMPTS` 7→15 và `_MAX_TTS_SEGMENTS` 8→16. Được user đồng ý, tự tay kill + khởi động lại tiến
    trình uvicorn cổng 8000 để nạp bản sửa (rủi ro: có thể ngắt việc phiên kia đang làm, tương tự lỗi
    `FACTORY_INTERRUPTED` đã gặp ở tập 17) — bản sửa có hiệu lực (lỗi đổi thành "after 15 attempts") nhưng với
    174 beat vẫn còn fail. **Giải pháp cuối cùng (theo đề nghị của user): tách đôi** thành Long02 (chương 11-15,
    100 beat, ~6 phút) và Long03 (chương 16-20, 74 beat, ~5 phút) — **cả hai đều qua ngay lần render đầu tiên**,
    xác nhận beat count càng nhỏ càng ổn định. File build script dùng chung `build_long_11_20.py`
    (định nghĩa dữ liệu 10 chương) + `build_long_split.py` (chia đôi, build riêng từng phần) — chỉ lưu trong
    scratchpad phiên chat, chưa đưa vào repo vì là công cụ một lần, không phải quy trình lặp lại thường xuyên như
    `recap.py`.
  - Mục lục thời gian (`recap.py timestamps <id> --script <file>`):
    - Long02 (project 141): 0:00 Tập 11: U Minh Cốc tìm tới / 1:09 Tập 12: Ván cờ chính trị / 2:15 Tập 13: Huyết
      Anh ra đời / 3:24 Tập 14: Vạch trần gián điệp / 4:34 Tập 15: Ngũ cấp trận sư
    - Long03 (project 142): 0:00 Tập 16: Âm mưu bắt cóc / 0:56 Tập 17: Bắt sống tiểu trại chủ / 1:50 Tập 18: Hôn
      phu là chủ mưu / 2:41 Tập 19: Sự thật về sơn chủ / 3:41 Tập 20: Thảm sát trong rừng
- 2026-09-30: chương 20 (`dqgl_ep20`) — `cut` ra 73 khung, không có khung rác. Viết tay `ep20/script.json`
  (14 beat). `build --script` tạo project 139, **render fail 0 lần** (qua ngay lần 1, chỉ cần force-continue qua
  NEEDS_REVIEW như thường lệ). job_199, **Final QA PASS 100 (37.45s, 1080×1920)**.
- 2026-09-30: chương 19 (`dqgl_ep19`) — `cut` ra 76 khung, không có khung rác. Viết tay `ep19/script.json` (17 beat).
  `build --script` tạo project 138, **render fail 1 lần** ở GENERATING_VOICE (edge_tts "No audio was received", cùng
  lỗi tập 18), retry lần 2 qua ngay. job_198, **Final QA PASS 100 (44.98s, 1080×1920)**.
- 2026-09-30: chương 18 (`dqgl_ep18`) — `cut` ra 70 khung, không có khung rác. Viết tay `ep18/script.json` (13 beat).
  `build --script` tạo project 137, **render fail 2 lần liên tiếp** ở GENERATING_VOICE (`TTS_GENERATION_FAILED`:
  "No audio was received" từ edge_tts) dù lần này **không có project nào khác đang render song song** — test gọi
  edge_tts trực tiếp (ngoài app) vẫn thành công, nên nhiều khả năng là rate-limit/flake phía dịch vụ Microsoft chứ
  không phải do tranh chấp tài nguyên như tập 17. Retry lần 3 mới qua được. job_196, **Final QA PASS 100 (38.98s,
  1080×1920)**.
- 2026-09-30: chương 17 (`dqgl_ep17`) — `cut` ra 81 khung, không có khung rác. Viết tay `ep17/script.json` (15 beat).
  `build --script` tạo project 136, **render fail 3 lần liên tiếp** ở bước GENERATING_VOICE (lỗi
  `FACTORY_INTERRUPTED` do backend bị restart giữa chừng bởi phiên khác đang code song song, sau đó
  `TTS_GENERATION_FAILED`/`UNEXPECTED_ERROR` — file tạm `seg_NNN.wav/mp3` không tìm thấy, đúng lúc project khác
  (133) cũng đang GENERATING_VOICE cùng lúc, nghi ngờ tranh chấp tài nguyên edge_tts/thư mục tạm dùng chung). Xử lý
  bằng cách chờ rồi tạo factory-run mới (không phải retry) — lần thứ 4 mới qua được. job_195, **Final QA PASS 100
  (40.36s, 1080×1920)**. Ghi chú cho lần sau: nếu voice fail liên tục kiểu này, kiểm tra có project nào khác đang
  GENERATING_VOICE cùng lúc trước khi coi là lỗi thật.
- 2026-09-30: chương 16 (`dqgl_ep16`) — `cut` ra 79 khung, không có khung rác. Viết tay `ep16/script.json` (15 beat,
  cân đối 2 mạch truyện: từ chối cung phụng + âm mưu bắt cóc Lạc Vân Thường). `build --script` tạo project 135,
  job_194, **Final QA PASS 100 (43.0s, 1080×1920)**.
- 2026-09-30: chương 15 (`dqgl_ep15`) — `cut` ra 86 khung, không có khung rác. Viết tay `ep15/script.json` (17 beat).
  `build --script` tạo project 134, job_193, **Final QA PASS 100 (47.78s, 1080×1920)**.
- 2026-09-29: chương 14 (`dqg_ep14`, ảnh đã tải sẵn từ trước) — `cut` cho 93 khung, không có khung rác nào cần xóa
  (không có credit dịch/QR quảng cáo như các chương khác). Claude đọc `_recap/sheets/`, viết tay `ep14/script.json`
  (20 beat). `build --script` tạo project 132, job_192, **Final QA PASS 100 (52.65s, 1080×1920)**.
- 2026-09-29: chương 13 — thử nghiệm đầu tiên với `GPT_SCRIPT_PROMPT.md` (anh dán link chương cho GPT, GPT trả về
  JSON). Kết quả: **script bịa hoàn toàn**, không khớp ảnh thật (xem chi tiết ở mục nhân vật chương 13 phía trên).
  Claude tự đọc lại `_recap/sheets/` (81 khung sau khi xóa 6 khung rác: credit dịch, thông báo lịch ra chap, QR
  quảng cáo, quảng cáo truyện khác, credit dịch giả, kênh Ham Truyện TV) và viết tay `ep13/script.json` (20 beat).
  `build --script` tạo project 129, job_188, **Final QA PASS 100 (52.52s, 1080×1920)**.
- 2026-09-29: chương 12 (`dqg_ep12`, ảnh đã tải sẵn từ trước qua UI `/manhua-fetch` mới) — `cut` ra 96 khung, xóa 1
  khung quảng cáo "Ham Truyện TV" (p096) còn lại 95. Viết tay `ep12/script.json` (20 beat). `build --script` tạo
  project 128, job_187, **Final QA PASS 100 (50.04s, 1080×1920)**.
  - Phát hiện bug thật khi `build`: `tools/manhua_recap/recap.py` thiếu `import urllib` (`NameError: name 'urllib'
    is not defined` ở hàm `call()`), do một phiên khác vừa refactor file này (commit `f790a42`, chuyển logic fetch
    sang `app/modules/manhua/fetch.py` + thêm trang `/manhua-fetch` trong app) — refactor cắt file từ 602 xuống 440
    dòng và làm rớt mất import. Đã tự sửa thêm lại `import urllib.error` / `import urllib.request` ở đầu file,
    `build` chạy lại bình thường. **Chưa commit** — cần xác nhận với chủ dự án trước khi commit fix này.
- 2026-09-29: chương 11 (`dqg_ep11`, ảnh đã tải sẵn từ trước) — `cut` cho 91 khung, không có khung rác nào cần xóa
  (khác với ep1/ep2). Claude đọc `_recap/sheets/`, viết tay `ep11/script.json` (23 beat), `build --script` tạo project 124,
  job_183, render xong: **51.44s, 1080×1920, Final QA PASS 100**.
  - Factory-run dừng ở `NEEDS_REVIEW` sau khi render xong bước Motion — đây là hành vi bình thường của mọi project
    manhua_recap (ep1/ep2/Long01 trước đó cũng vậy): Quality Gate chấm điểm "độ khớp ảnh" theo kiểu AI tự tìm ảnh
    trong thư viện, không hiểu rằng `build` đã gán tay từng panel nên luôn báo cần review cho toàn bộ số beat. Xử lý
    bằng `POST /factory-runs/{run_id}/continue?force=true` (lưu ý: `force` là **query param**, không phải trường
    trong JSON body).
  - Bug nhỏ phát hiện khi sửa tiêu đề: `derive_title` (`app/modules/metadata/service.py`) coi tiêu đề như tên file
    nên strip ký tự `?` (bất hợp pháp trong tên file Windows) — nghĩa là tiêu đề kết bằng "!?" theo công thức kênh
    **luôn bị mất dấu `?`** ở trường `package.title` (dùng khi publish thật lên YouTube), kể cả ở ep1/ep2 trước đó,
    chỉ là chưa ai để ý vì chưa publish. Không phải lỗi do build lần này gây ra, không tự sửa code — cần bàn với chủ
    dự án có muốn đổi công thức tiêu đề (bỏ `?` cuối) hay sửa `derive_title` để cho phép `?`.
- 2026-09-29: bản **tiếng Hàn** của tập 11 — `recap.py build` chỉ hard-code tiếng Việt (`content_language: "vi"` trong
  `cmd_build`), nên bản KR được build thủ công qua API thay vì CLI: dịch tay `ep11/script_ko.json` (23 beat, cùng
  panel/asset_id đã đăng ký từ bản VI, không tải/đăng ký ảnh lại), tạo project bằng `content_language: "ko"` (backend
  tự đổi provider sang edge_tts + `voice.language: "ko"`, nhưng **không** tự đổi `voice_id` — phải set tay
  `voice_id: "ko-KR-InJoonNeural"`, nếu không sẽ đọc tiếng Hàn bằng giọng vi-VN-NamMinhNeural cũ của template).
  Project 125 / job_184, **Final QA PASS 100 (71.0s, 1080×1920)** — dài hơn bản VI (51.44s) dù cùng nội dung, vì pace
  ước tính trước-giọng-đọc (5.1 âm tiết/s) chỉ đúng cho tiếng Việt, thời lượng thật do bước Voice đo lại theo giọng
  Hàn. Tên nhân vật dịch theo âm Hán-Việt→Hán-Hàn suy đoán (chưa có bản dịch Hàn chính thức để đối chiếu): Trác Phàm
  → 탁범, Lạc Vân Thường → 낙운상, Lạc gia → 낙가, Tôn gia → 손가, U Minh Cốc → 유명곡, U Tuyền → 유천, U Minh Trảo →
  유명조, Huyết Ảnh Chưởng → 혈영장, Ma Đạo → 마도. Tên series tạm dịch "집사가 된 마황" (chưa có tên Hàn chính thức).
- 2026-09-28: render Long 01: project 121, job_181, dài 10:17, 1920x1080, QA PASS 100.
  Mục lục thời gian (in bằng `recap.py timestamps 121 --script ...long01/script.json`):
  0:00 Mở đầu: Ma Hoàng bị phản bội / 1:29 Tâm ma: bị trói vào Lạc gia / 2:26 Rừng Sương Mù: cái bẫy chết người /
  3:47 Kế lừa: Trác Phàm bán chủ? / 4:52 Đột phá: Ma Hoàng giấu nghề / 5:42 Phong Lâm Thành: viên ngọc giả /
  6:39 Luyện Huyết Anh / 7:07 Thái phủ trở mặt / 7:34 Ma Hoàng nổi giận / 8:15 Ngự Hạ Thất Thế Gia / 9:05 Thượng Cổ Trận Thức Đồ
- 2026-09-28: tắt nhạc nền cho template manhua, render lại tập 1–2 (project 117/118, jobs 179/180).
- 2026-09-28: phân tích truyện, viết tay kịch bản tập 1–2 (Claude đọc 31 ảnh đọc, 180 khung).
