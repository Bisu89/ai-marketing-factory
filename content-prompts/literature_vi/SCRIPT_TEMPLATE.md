# SCRIPT_TEMPLATE — khuôn kịch bản tập 14–16 phút (dùng cho mọi tác phẩm)

Đọc `CHANNEL.md` (nguyên tắc) và `MAPPING.md` (lưu vào `spec.json` thế nào) trước.

**Chuẩn thời lượng (chốt 2026-10-12, áp dụng cho mọi tập sau, thay chuẩn cũ 6–9 phút):** mục tiêu khoảng 15 phút,
khoảng chấp nhận 14–16 phút. Thời lượng thật đo từ audio, **không bao giờ** chỉ từ số chữ. Không kéo dài bằng đọc
chậm bất thường, lặp ý, câu triết lý sáo rỗng hoặc khoảng nghỉ hình ảnh — chỉ mở rộng bằng diễn biến, chi tiết tác
phẩm, phân tích và hình ảnh có giá trị thật.

## 1. Năm nhóm biên tập → bảy phần kỹ thuật (gợi ý, không phải khuôn cứng)

Mỗi tác phẩm có thể đặt tên 5 nhóm biên tập khác nhau (tiêu đề theo nội dung riêng của tác phẩm đó, không sao
chép tiêu đề của tập khác). Nhóm biên tập là **lớp biên tập**, không phải trường trong spec; mỗi nhóm được chia vào
đúng các `kind` kỹ thuật mà máy dựng đòi (xem mục 2 và `MAPPING.md`). Một nhóm trải qua nhiều `kind` thì chia nhỏ
theo `kind`, không gộp cứng; máy dựng **bắt buộc đủ 7 `kind`** (hook, context, timeline, evidence, turning_point,
consequences, conclusion), thiếu phần nào kiểm tra kịch bản báo `missing_section`.

| Nhóm biên tập (gợi ý, đặt tên theo tác phẩm) | `kind` kỹ thuật | Tỉ trọng gợi ý trên ~15 phút |
|---|---|---|
| 1. Mở đầu | `hook` | ~1 phút: một khoảnh khắc/câu hỏi thật, không tiết lộ hết kết cục |
| 2. Nhân vật và bối cảnh | `context` | ~2–3 phút: ai, ở đâu, lúc nào, vì sao người xem cần quan tâm |
| 3. Diễn tiến + xung đột/cơ chế xã hội | `timeline` + `evidence` | ~5–6 phút: các mốc theo thứ tự, rồi xung đột chính kèm dẫn chứng; **không liệt kê sự kiện khô khan** — cho thấy cơ chế (ai có lợi, ai mất) |
| 4. Bước ngoặt cảm xúc trung tâm | `turning_point` | ~3–4 phút: trung tâm cảm xúc của tập, dành đủ thời gian, không vội |
| 5. Bi kịch/cao trào + góc nhìn riêng | `consequences` + `conclusion` | ~3–4 phút: hệ quả thật, rồi bình luận gốc + câu hỏi mở |

Tỉ trọng ở trên là điểm xuất phát để cân câu chuyện, không phải mốc giây cố định; mốc thời gian thật luôn lấy từ
audio sau khi dựng storyboard. Tác phẩm ngắn/ít nhân vật có thể gộp nhóm 2 và 3; tác phẩm nhiều tuyến có thể tách
nhóm 3 thành hai đoạn `timeline`/`evidence` dài hơn — miễn giữ đủ 7 `kind`.

## 2. Ba chế độ lời đọc (nhãn ghi ở đầu mỗi đoạn trong bản nháp)
| Chế độ | Dùng cho | Lưu trong spec |
|---|---|---|
| **NGƯỜI KỂ / PHÂN TÍCH** | kể sự kiện của tác phẩm; phân tích dựa trên văn bản | `factual: true`, gắn khẳng định có nguồn là trích đoạn nguyên văn |
| **GÓC NHÌN NHÂN VẬT** | tiếng nói nội tâm sáng tạo ở ngôi thứ nhất/gần nhân vật | `factual: false`; **không** đặt trong ngoặc kép như lời nguyên tác; ghi chú "diễn giải" |
| **BÌNH LUẬN CỦA CHỦ KÊNH** | quan điểm của người làm kênh | `factual: false`; nêu lý lẽ và chỉ dẫn chi tiết trong văn bản |
Chuyển từ GÓC NHÌN NHÂN VẬT sang BÌNH LUẬN phải có câu chuyển rõ ("Đó là điều mình tưởng tượng; còn trong truyện thì…").
Nên đặt 1 GÓC NHÌN NHÂN VẬT ở mỗi điểm chuyển biến tâm lý lớn của nhân vật chính (ví dụ: lúc trở về/xuất hiện lại,
lúc nhận ra chỗ đứng của mình, lúc một biến cố làm nhân vật tỉnh ra, lúc đón nhận một cử chỉ tốt hiếm có, lúc hy
vọng, lúc đối diện sự từ chối/mất mát) — không bắt buộc đủ cả sáu, chọn những điểm tác phẩm thật sự có.

## 3. Mẫu cho mỗi cảnh/đoạn (điền vào bản nháp `script.md`)
```
[Phần] hook | context | evidence | turning_point | consequences | conclusion
Mã cảnh: S### (do công cụ gán sau khi dựng storyboard)      Ước tính: ~__ giây (số thật lấy từ audio)
Mục đích kể: ...
Chế độ: NGƯỜI KỂ | GÓC NHÌN NHÂN VẬT | BÌNH LUẬN
Lời đọc: ...
Dẫn chứng/nguồn: (tên tác phẩm, chương/đoạn; trích đoạn nguyên văn nếu dùng) | hoặc "—"
Hành động nhân vật: ...      Cảm xúc chủ đích: ...
Hình: (mô tả theo VISUAL.md, mã màu nền)      Chữ trên màn hình: (≤ 4 từ, cắt từ lời đọc)
Âm thanh gợi ý: ...      Chuyển cảnh: ...
Trạng thái nội dung: SỰ KIỆN TÁC PHẨM | BỐI CẢNH CÓ NGUỒN | DIỄN GIẢI | LỜI DẪN NỐI
```
Bốn trạng thái nội dung ứng với bốn loại ở `CHANNEL.md`; chỉ hai loại đầu được `factual: true`.

## 4. Văn phong
- Tự nhiên khi đọc to: câu ngắn, hình ảnh cụ thể, hành động hơn khẩu hiệu; giải thích tên/tình huống lạ trong một câu.
- Không mở/kết lặp khuôn; không "bài học rút ra là…"; không bi lụy mà văn bản không đỡ; **không bịa trích dẫn**.
- Tránh lạm dụng các khuôn câu công thức kiểu "Có những điều...", "Đó là lúc hắn/nàng nhận ra...", "Không phải vì...,
  mà vì...", "Điều đáng sợ nhất không phải...", "Và đó chính là bi kịch..." — chỉ dùng khi thật sự cần, không dùng
  làm khung lặp lại cho mọi đoạn bình luận.
- Năm viết 4 chữ số; tên riêng giữ nguyên chính tả tác phẩm; tên nhân vật nhất quán suốt tập.
- Con số muốn hiện lớn viết bằng chữ số (xem luật storyboard của Vox template).
- Mỗi tập nên có ít nhất một chi tiết "cơ chế" thật (ai có lợi, quy tắc ngầm nào đang vận hành), không chỉ dừng ở
  kể lại biến cố của riêng một nhân vật — tác phẩm nào có cho phép.

## 5. Nguồn và đối chiếu
Mỗi tập có mục: (1) văn bản tác phẩm đã lấy (nguồn, ngày truy cập); (2) bối cảnh có nguồn; (3) diễn giải và ai đưa ra; (4) việc cần kiểm chứng. Chưa kiểm chứng được thì **không viết** nội dung đó như sự thật.

## 6. Đo thời lượng bằng audio thật (độc lập với 5 cổng)
Đo độ dài **không đi qua state machine/5-cổng** của app (cổng 1–4 cần chủ kênh tự duyệt trước khi chạm TTS chính
thức). Cách làm: tách phần lời đọc thuần khỏi tiêu đề/ghi chú/nhãn chế độ → đếm số từ → chạy `edge-tts` **độc lập
ngoài app** (gọi trực tiếp thư viện `edge_tts`, không qua `backend/app/modules/documentary`), giọng `vi-VN-NamMinhNeural`,
lưu file tạm trong scratch dir → đo bằng `ffprobe`. `edge-tts` hay báo lỗi `NoAudioReceived` ngẫu nhiên trên một yêu
cầu dài; chia theo từng đoạn/cảnh (khớp cách app chia ~350–900 ký tự) và thử lại tối đa vài lần mỗi đoạn, cộng thời
lượng các đoạn lại, giống cách làm trong bước hiệu chỉnh tập Chí Phèo (xem `episodes/chi-pheo-ep01/README.md`). Đây
chỉ là bước **hiệu chỉnh độ dài kịch bản**, không phải sản xuất audio chính thức của dự án (audio chính thức vẫn
tạo trong app, sau khi qua cổng 3, theo `RULES.md` mục 5).
Nếu audio ngắn hơn mục tiêu, mở rộng nội dung có giá trị (diễn biến/phân tích/chi tiết cơ chế thật), không lặp ý
hay thêm triết lý sáo rỗng. Nếu dài quá 16 phút, cắt lặp ý trước khi cắt điểm cảm xúc quan trọng.

## 7. Danh sách kiểm tra cuối (trước cổng 2)
- [ ] Đúng với tác phẩm (từng sự kiện có dẫn chứng); trích dẫn cắt từ nguồn thật.
- [ ] Mạch kể liền lạc; mở đầu có câu hỏi thật.
- [ ] Có phân tích thật sự (không chỉ tóm tắt) và **bình luận gốc của chủ kênh**.
- [ ] Giọng Việt tự nhiên khi đọc to; không câu công thức.
- [ ] Không khẳng định thiếu nguồn; diễn giải được gắn nhãn.
- [ ] Trích dẫn/ảnh an toàn bản quyền.
- [ ] Thời lượng đo bằng audio thật (mục 6) nằm trong khoảng 14–16 phút, hoặc có lý do kỹ thuật ghi rõ nếu chưa đo được.
