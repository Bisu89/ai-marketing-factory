# Manhua Series — tổng hợp tính năng đã xây (tài liệu bàn giao)

File này gom lại **toàn bộ tính năng đã làm** cho dự án manhua recap, để đọc một file là đủ
tiếp tục công việc ở phiên chat mới, không cần lịch sử hội thoại cũ.

- Cách dùng hàng ngày (quy trình từng bước, setup máy mới, định dạng `script.json`): xem
  [`README.md`](README.md).
- Trạng thái từng truyện/tập, nhân vật, ghi chú đọc truyện: xem `<ten-truyen>/SERIES.md`
  (ví dụ [`dai-quan-gia-la-ma-hoang/SERIES.md`](dai-quan-gia-la-ma-hoang/SERIES.md)).
- Lịch sử kỹ thuật đầy đủ (vì sao làm, bug đã sửa): `docs/features/153-manhua-recap.md` ở gốc repo.

## 1. Công cụ `tools/manhua_recap/recap.py`

Chạy bằng python trong `.venv` của backend, backend phải đang chạy ở cổng 8000
(đổi bằng biến môi trường `MANHUA_API` nếu cần).

| Lệnh | Việc làm | Tốn phí? |
|---|---|---|
| `fetch <link> <thư_mục> [--count N]` | Tải ảnh các trang của một chương (và N-1 chương tiếp theo) | Miễn phí |
| `cut <thư_mục>` | Ghép các trang thành dải dài, cắt theo khe trắng thành từng khung | Miễn phí |
| `sheets <thư_mục>` | Ghép 6 khung/ảnh, đánh số, để Claude đọc và tự viết kịch bản | Miễn phí |
| `script <thư_mục> [--mode chapter\|premise] [--no-commentary]` | **AI (OpenAI) tự đọc tranh và viết kịch bản** | **Có phí** (~0.25–0.5 USD/lần) |
| `build <thư_mục> [--script FILE] [--captions color\|yellow] [--commentary-voice V]` | Đăng ký ảnh vào Asset Library, tạo project, bắt đầu render | Miễn phí |
| `timestamps <project_id> --script FILE` | In mục lục thời gian YouTube từ các `section` trong kịch bản | Miễn phí |

**Quy trình khuyên dùng (không tốn phí AI):** `fetch → cut → sheets` rồi nhờ Claude đọc sheets
và tự viết `script.json` tay (lưu trong `manhua-series/`, không phải trong `manhua-recap/`),
sau đó `build --script <file đó>`. Lệnh `script` (gọi OpenAI) chỉ dùng khi muốn tự động hoàn
toàn, chấp nhận tốn phí và chất lượng thấp hơn Claude đọc tay.

### 1.1 `fetch` — hỗ trợ 3 nguồn

| Trang | Cách lấy ảnh | Giới hạn |
|---|---|---|
| **manhuavn2.com** | `data-original=` trong HTML | Chương VIP (`isAccessibleForFree:false`) bị chặn, không tải. Một số chương nằm trên CDN `img02.g5img.top` trả về **403** khi tải từ ngoài (hotlink protection) — phải tải tay bằng extension trình duyệt. |
| **cotruyenday.com** | Link `images.jino277.work/prod/chapters/...` trong HTML (URL có khoảng trắng, được percent-encode trước khi tải) | Chương miễn phí giới hạn (Đại Quản Gia: chương 0–10); chương sau đó cần đăng nhập, không có ảnh. |
| **zettruyen\*.com** (zettruyen2, …) | Ảnh trên CDN `zetimage.com`, cần đúng header Referer từ trang gốc mới tải được (đã xử lý trong tool) | Chỉ hoạt động khi trang cho phép; nếu CDN vẫn chặn, phải tải tay. |

Trang **sangchanhteam.com** thử nhưng **không hỗ trợ** — chặn tải hoàn toàn, phải tải tay 100%.

**Tự động lọc ảnh rác lặp lại** (banner quảng cáo, logo, thông báo nhóm dịch xuất hiện y hệt ở
mọi chương): mỗi trang tải về được băm bằng SHA1; nếu trùng khớp SHA1 với một trang khác đã
thấy (trong cùng lần chạy hoặc lần chạy trước, lưu cache ở `tools/manhua_recap/_common_hashes.json`,
không đưa lên git) thì bị bỏ, không đánh số. Ngoài ra còn dùng **perceptual hash** (ảnh xám
16×16, khoảng cách Hamming ≤ 6 bit) để bắt cả trường hợp ảnh rác giống hệt nhưng bị nén lại
với chất lượng khác (byte khác nhau nhưng nhìn giống nhau) — trường hợp SHA1 không bắt được.

### 1.2 `cut` — cắt khung tranh

- Ghép tất cả trang thành một dải ảnh dọc dài, tìm các **hàng gần như một màu** (khe trắng/đen
  giữa hai khung) để cắt.
- Khung nào **cao hơn 2 lần chiều rộng** (nhiều khung dính liền vì không có khe trắng, ví dụ
  bong bóng thoại tràn qua khung) được **tự cắt thêm** ở chỗ ít chi tiết nhất.
- Ghi `_recap/panel_pages.json`: mỗi khung → tên trang gốc (và số chương, nếu `fetch --count`
  tải nhiều chương). Dùng để `sheets` hiển thị đúng số chương cạnh mỗi khung.
- Tên khung 3 chữ số (`p001.jpg`) bình thường, **4 chữ số** (`p0001.jpg`) khi có trên 1000 khung
  (trường hợp gộp nhiều chương cho video dài).
- Tự xóa khung quá nhỏ hoặc gần như trống (không phải nội dung thật).

### 1.3 `sheets` — ảnh để Claude đọc

- Mỗi ảnh gồm 6 khung, có tên file đỏ đè lên (`p0045.jpg`), kèm `[cNNN]` nếu ảnh đến từ chương
  khác với đa số (giúp Claude biết đang đọc chương nào khi gộp nhiều chương).
- Đây là cách Claude tự đọc tranh **không tốn phí OpenAI** (khác với lệnh `script`).

### 1.4 `script` — AI tự viết kịch bản (endpoint `POST /manhua-recap/script`)

- Gọi `gpt-5.6-luna` qua `call_structured` của app, kèm ảnh từng khung (giảm cỡ ảnh nếu trên
  80 khung, để không vượt giới hạn request).
- Hai chế độ:
  - **`chapter`** (mặc định): tóm tắt đúng 1 chương, kết ở đoạn cao trào/phản ứng.
  - **`premise`**: dùng khung của **nhiều chương đầu** (`fetch --count N`), viết kiểu "bán ý
    tưởng series" — mở bằng nghịch lý "X này...", quay lại đầu truyện, đẩy tình huống lên,
    **kết lửng (cliffhanger)** để câu view sang video sau.
- **Bình luận kênh (`kind: commentary`)**: mặc định bật (`--no-commentary` để tắt). Ít nhất 2
  câu, câu cuối cùng phải là bình luận (chế độ chapter) hoặc phải LÀ đoạn kể (chế độ premise,
  không kết bằng bình luận). Chiếm tối thiểu 5–8% tổng lời kể. Lý do: chính sách kiếm tiền của
  YouTube (cập nhật 07/2025) cấm video "chỉ đọc lại nội dung người khác", nhưng cho phép "có
  thêm bình luận/góc nhìn riêng".
- Panel phải theo **thứ tự tăng dần**, không dùng lại khung. Sai thì tự động gọi lại tối đa
  2 lần (kèm lỗi cụ thể để AI tự sửa).
- Độ dài tính theo ngân sách âm tiết (`SYLLABLES_PER_SECOND = 5.1`), sai lệch quá 1.3 lần thì
  bị từ chối, phải viết ngắn lại.

### 1.5 `build` — tạo project và render

- Đăng ký từng khung làm Asset (tag `manhua_recap`), tránh đăng ký trùng khung đã có.
- Đọc `template` trong `script.json` để chọn template Short (`manhua_recap_vi`, mặc định) hay
  Long (`manhua_recap_long_vi`).
- Beat có `kind: commentary` được gán `voice_id` khác (mặc định `vi-VN-HoaiMyNeural`, đổi bằng
  `--commentary-voice`, hoặc `same` để dùng chung giọng kể).
- Set `title` / `description` / `hashtags` từ `script.json` làm package overrides (app không
  tự viết AI metadata cho 2 template này — xem mục 2).
- Bắt đầu render ngay, trừ khi có `--no-render`.

### 1.6 `timestamps` — mục lục thời gian cho video dài

- Đọc `section` trên từng beat trong `script.json`, khớp với **thời điểm bắt đầu thật** của
  beat đó sau khi Voice stage render xong (không phải ước tính), in ra dạng `M:SS Tên phần`
  để dán vào mô tả hoặc bình luận ghim YouTube.

## 2. Tính năng đã thêm vào backend (dùng chung, không riêng manhua)

| Tính năng | Ở đâu | Mô tả |
|---|---|---|
| **Preset phụ đề `word_pop`** | `caption/ass_writer.py`, `video_composer/subtitles.py` | Mỗi lần hiện đúng 1 chữ, in hoa, màu **ngẫu nhiên có seed** (không lặp lại 2 chữ liên tiếp, nhưng render lại thì ra đúng màu cũ — không phá cache) |
| **Preset `word_pop_yellow`** | như trên | Giống `word_pop` nhưng luôn màu vàng (giống kênh NBToon tham khảo) |
| **`motion.fit_mode = "blur_fill"`** | `modules/motion/renderer.py`, `modules/beat/schemas.py` | Đặt cả khung tranh (không cắt xén) vào giữa, nền là chính khung đó phóng to làm mờ — giữ được bong bóng thoại ở mép, khác với kiểu cắt vừa khung (`cover`, mặc định cũ) |
| **`Beat.voice_id`** (giọng riêng từng beat) | `modules/beat/schemas.py`, `voice_generate.py`, `voice/providers.py` | Một project có thể có nhiều giọng đọc; các beat liền kề cùng giọng được gộp lại rồi mới gọi TTS, giữ nguyên mốc thời gian từng từ để phụ đề vẫn khớp |
| **Sửa lỗi treo edge_tts** | `voice/providers.py` | Gọi TTS có giới hạn 45 giây/lần thử, tránh treo vô thời hạn khi máy chủ Microsoft không phản hồi (ảnh hưởng **mọi** project dùng edge_tts, không riêng manhua) |

## 3. Hai template dựng sẵn

| | `manhua_recap_vi` (Short) | `manhua_recap_long_vi` (video dài) |
|---|---|---|
| Khung hình | 9:16 dọc | 16:9 ngang |
| Phụ đề | `word_pop` (1 chữ, màu ngẫu nhiên) | `cinematic` (câu đầy đủ, kiểu phim) |
| Cắt/đặt khung | `blur_fill` | `blur_fill` |
| Giọng kể | `vi-VN-NamMinhNeural` tốc độ **1.6** | `vi-VN-NamMinhNeural` tốc độ **1.3** |
| Nhạc nền | Tắt | Tắt |
| AI tự viết tiêu đề/mô tả/hashtag | Tắt (lấy từ `script.json`) | Tắt (lấy từ `script.json`) |
| Độ dài mục tiêu | ~50–60 giây | ~10–15 phút |

**Vì sao tắt nhạc nền:** thư viện nhạc có sẵn không có bài phù hợp thể loại tu tiên/huyền
huyễn, lần thử đầu bị gán nhầm nhạc kinh dị/nhạc cầu nguyện.

**Vì sao tắt AI metadata:** tiết kiệm phí, và để tiêu đề/mô tả/hashtag do Claude viết tay theo
đúng công thức (nghịch lý + "!?", có link tập trước/sau) thay vì AI viết chung chung.

## 4. Quy tắc kịch bản đã rút ra (phân tích kênh NBToon tham khảo, xem `SERIES.md` để biết chi tiết)

- Mở đầu bằng công thức **"<Nhân vật> này" + một nghịch lý** hiểu ngay trong một câu.
- Quay lại đầu truyện bằng "Chuyện bắt đầu khi...", rồi đẩy tình huống lên.
- **Kết lửng**, không giải quyết xong xuôi, để kéo sang tập sau.
- Có bình luận riêng của kênh (giọng khác) — vừa tăng tính "review" (đúng chính sách YouTube),
  vừa tạo bản sắc riêng.
- Tiêu đề kết bằng "!?", có 3–6 hashtag.

## 5. Trạng thái hiện tại (xem chi tiết trong `SERIES.md` của từng truyện)

### Đại Quản Gia Là Ma Hoàng (`dai-quan-gia-la-ma-hoang/`)
- **Ep01** (chương 1) — kịch bản Claude tự viết, đã render, Final QA PASS 100.
- **Ep02** (chương 2) — kịch bản Claude tự viết, đã render, Final QA PASS 100.
- **Ep03** (chương 3–6) — đã tải ảnh (418 khung, thư mục `manhua-recap/dqg_ep3`), **chưa viết
  kịch bản**.
- **Long01** (video dài, chương 1–10) — 1039 khung, Claude đọc tay toàn bộ, kịch bản 170 beat /
  11 phần, đã render (~10 phút 17 giây), Final QA PASS 100. Ghi chú đọc chi tiết từng chương ở
  `long01/notes.md` — **dùng lại được** để viết Short các tập 3–10 sau này mà không cần đọc
  tranh lại từ đầu.

### Vạn Cổ Chí Tôn
- Chỉ có các bản thử ban đầu do **OpenAI viết** (không phải Claude đọc tay), dùng để kiểm tra
  tính năng lúc mới xây dựng tool. Không phải nội dung chính thức của kênh.

## 6. Việc còn tồn đọng / cần lưu ý khi tiếp tục

1. **Phụ đề video dài hơi nhỏ**, đôi lúc đè lên mép dưới bong bóng thoại của khung — chưa chỉnh
   lại cỡ chữ/nền cho preset `cinematic` trên khung 1920×1080.
2. **Ep03 của Đại Quản Gia** đã có ảnh, cần Claude đọc `_recap/sheets/` rồi viết
   `ep03/script.json` (có thể tách chương 3–4 và 5–6 thành 2 tập riêng, xem gợi ý cũ trong
   `SERIES.md`).
3. **manhua-recap/** (ảnh tranh) không đưa lên git — máy khác phải `fetch` + `cut` lại. Danh
   sách khung rác đã xóa tay (nếu có) được ghi trong mục "Khung đã xóa" của `SERIES.md`, cần
   xóa lại y hệt để tên khung khớp với `script.json` đã lưu.
4. Có một thay đổi **chưa commit** ở `backend/app/modules/beat/schemas.py` (tắt nhạc nền cho
   template `zombie_system`, không liên quan tới manhua) — kiểm tra trước khi commit dọn dẹp.
