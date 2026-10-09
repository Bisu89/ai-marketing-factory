# Chi phí

**Thiết kế để gần 0 đồng cho mỗi tập.** Giá không bao giờ được hardcode: giá ElevenLabs do bạn đặt (`usd_per_1k_chars`); chưa đặt ⇒ "chưa biết", không ghi $0 giả.

| Bước | Chi phí | Ghi chú |
|---|---|---|
| Nghiên cứu, kịch bản `mock`, storyboard | 0 | |
| Kịch bản `llm` | token của provider AI bạn đã cấu hình | tùy chọn; UI hỏi xác nhận |
| Ảnh tư liệu | 0 | kiểm tra giấy phép |
| Ảnh AI | theo gói công cụ bạn dùng (vd. thuê bao ChatGPT) | **app không gọi API sinh ảnh**; bạn tạo tay từ CSV |
| Giọng `edge` | 0 | miễn phí nhưng chập chờn (có retry) |
| Giọng `elevenlabs` | theo ký tự × giá gói của bạn | ~9–10 nghìn ký tự cho 10 phút; xem ước tính, xác nhận trước khi chạy |
| Căn chỉnh | 0 | timestamp của TTS, hoặc Whisper chạy máy bạn (CPU) |
| Render | 0 API; tốn CPU/thời gian | đo thật trên i5-12400: preview 50% đủ độ dài ~75 s; bản cuối 1080p 118 s ≈ 5 phút (~2.5× thời gian thực) |
| Nhạc nền | 0 nếu dùng nhạc miễn phí bản quyền bạn có | |

## Kiểm soát
- **Ngân sách dự án** (tùy chọn) chặn tạo audio khi `đã chi + ước tính > ngân sách` trừ khi `confirm=true`.
- **Sổ cái chi phí** (`documentary_usage`, chỉ thêm): ký tự và chi phí từng lần gọi, kể cả lần lỗi; lượt chưa biết giá được đếm riêng.
- **Giới hạn thử lại**: tối đa 3 lần/đoạn cho mỗi phiên bản văn bản+giọng.
- **Cache**: đoạn audio không đổi, kết quả căn chỉnh không đổi, và video render có cùng hash đầu vào đều không tính phí/không chạy lại.

## Chỉ để tham khảo: vì sao không dùng AI sinh ảnh/video cho từng cảnh
Dự án `vox-directer` (poster AI + image-to-video mỗi beat) ước ~$25–160 cho phim 9 phút tùy giá tính theo clip hay theo giây (tài liệu của nó tự mâu thuẫn),
cộng chữ vỡ trong ảnh AI và phụ thuộc một nhà cung cấp. Xem `docs/features/170-documentary-trial-run.md`.
