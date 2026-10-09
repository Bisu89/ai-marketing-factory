# SCRIPT_TEMPLATE — khuôn kịch bản tập 6–9 phút (dùng cho mọi tác phẩm)

Đọc `CHANNEL.md` (nguyên tắc) và `MAPPING.md` (lưu vào `spec.json` thế nào) trước. Thời lượng thật đo từ audio, không từ số chữ (≈ 130–150 từ/phút giọng edge).

## 1. Khung (mốc thời gian chỉ là điểm xuất phát)
| Phần | Loại phần trong máy dựng | Gợi ý |
|---|---|---|
| Mở đầu | `hook` | 0:00–0:35: một khoảnh khắc cụ thể + câu hỏi thật |
| Bối cảnh, nhân vật | `context` | –1:40: ai, ở đâu, lúc nào, vì sao người xem cần quan tâm |
| Xung đột chính + phân tích | `evidence` | –3:00: xung đột, kèm dẫn chứng thật; thẻ bằng chứng |
| Bước ngoặt | `turning_point` | –4:25 |
| Cao trào, hệ quả | `consequences` | –6:10 |
| Bình luận riêng | `conclusion` (nhóm đoạn 1) | –7:30: góc nhìn của chủ kênh, có lý lẽ |
| Kết, câu hỏi mở | `conclusion` (nhóm đoạn 2) | tổng thời lượng tự nhiên |
Máy dựng chỉ có 7 loại phần cố định; "bình luận riêng" và "kết" cùng thuộc `conclusion`, phân biệt bằng tiêu đề phần/ghi chú.

## 2. Ba chế độ lời đọc (nhãn ghi ở đầu mỗi đoạn trong bản nháp)
| Chế độ | Dùng cho | Lưu trong spec |
|---|---|---|
| **NGƯỜI KỂ / PHÂN TÍCH** | kể sự kiện của tác phẩm; phân tích dựa trên văn bản | `factual: true`, gắn khẳng định có nguồn là trích đoạn nguyên văn |
| **GÓC NHÌN NHÂN VẬT** | tiếng nói nội tâm sáng tạo ở ngôi thứ nhất/gần nhân vật | `factual: false`; **không** đặt trong ngoặc kép như lời nguyên tác; ghi chú "diễn giải" |
| **BÌNH LUẬN CỦA CHỦ KÊNH** | quan điểm của người làm kênh | `factual: false`; nêu lý lẽ và chỉ dẫn chi tiết trong văn bản |
Chuyển từ GÓC NHÌN NHÂN VẬT sang BÌNH LUẬN phải có câu chuyển rõ ("Đó là điều mình tưởng tượng; còn trong truyện thì…").

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
- Năm viết 4 chữ số; tên riêng giữ nguyên chính tả tác phẩm; tên nhân vật nhất quán suốt tập.
- Con số muốn hiện lớn viết bằng chữ số (xem luật storyboard của Vox template).

## 5. Nguồn và đối chiếu
Mỗi tập có mục: (1) văn bản tác phẩm đã lấy (nguồn, ngày truy cập); (2) bối cảnh có nguồn; (3) diễn giải và ai đưa ra; (4) việc cần kiểm chứng. Chưa kiểm chứng được thì **không viết** nội dung đó như sự thật.

## 6. Danh sách kiểm tra cuối (trước cổng 2)
- [ ] Đúng với tác phẩm (từng sự kiện có dẫn chứng); trích dẫn cắt từ nguồn thật.
- [ ] Mạch kể liền lạc; mở đầu có câu hỏi thật.
- [ ] Có phân tích thật sự (không chỉ tóm tắt) và **bình luận gốc của chủ kênh**.
- [ ] Giọng Việt tự nhiên khi đọc to; không câu công thức.
- [ ] Không khẳng định thiếu nguồn; diễn giải được gắn nhãn.
- [ ] Trích dẫn/ảnh an toàn bản quyền.
- [ ] Thời lượng dự kiến hợp lý (kiểm lại bằng audio thật sau khi tạo giọng).
