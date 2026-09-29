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
| 4–10, 13+ | theo arc | | | Chương 3–10 chỉ có bản dài (Long01); chương 11 là Short đầu tiên nối tiếp sau Long01, chưa làm Short riêng cho 3–10 |

## Video dài

| Video | Chương | Thư mục ảnh | Tiêu đề | Trạng thái |
|---|---|---|---|---|
| Long 01 | 1–10 | `manhua-recap/dqg_long01` (cotruyenday, `fetch --count 10`) | Ma Hoàng thành quản gia \| Tóm tắt chương 1-10 | ✅ script `long01/script.json` (170 beat, 11 phần), ghi chú đọc truyện chi tiết trong `long01/notes.md` |

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

Hai bản cũ do OpenAI viết (project 115/116, tiêu đề khác) được giữ để so sánh. Bản chính thức là bản Claude viết.

## Khung đã xóa trước khi cắt kịch bản

Đây là các khung logo, quảng cáo QR app và credit nhóm dịch.
Ở máy mới, sau khi chạy `cut` thì xóa lại đúng các file này để tên khung khớp với `script.json`.
Việc xóa không đổi tên các khung còn lại.

- `dqg_ep1`: p001, p002, p115, p116, p117
- `dqg_ep2`: p001, p002, p071, p072, p073

## Nhật ký

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
