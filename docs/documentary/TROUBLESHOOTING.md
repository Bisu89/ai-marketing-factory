# Xử lý sự cố

| Triệu chứng | Nguyên nhân đã gặp | Cách xử lý |
|---|---|---|
| `POST /storyboard/plan` trả **500** | DB dev thiếu cột (vd. `documentary_scene.assigned_hash`) vì DB được tạo ở giữa quá trình phát triển rồi bị đánh dấu "mới nhất" | Khởi động lại backend: migration `0015` bổ sung cột. Luật: **luôn thêm migration mới có kiểm tra tồn tại**; `test_migrations.py` bắt lệch lược đồ |
| Render báo "Remotion thoát với mã 1", log: `--props ... neither valid JSON nor a file path` | Đường dẫn tương đối (`./data/library`) + Remotion chạy ở thư mục khác | Đã sửa (đường dẫn tuyệt đối). Nếu tự gọi Remotion, dùng đường dẫn tuyệt đối |
| Python **sập** (access violation) khi nạp model Whisper | `ctranslate2 4.8.2` | Ghim `ctranslate2==4.6.0` và `setuptools<81` (xem `requirements.txt`) |
| Căn chỉnh Whisper lỗi trong app, ở máy có Python hệ thống cũ | Python của app có `ctranslate2` quá cũ | Dùng `method="tts"` (timestamp của TTS), hoặc chạy app bằng venv của repo |
| Cảnh timing "ƯỚC LƯỢNG" | TTS không trả timestamp và Whisper không dùng được | Căn chỉnh lại bằng Whisper hoặc nghe và chỉnh tay (ranh giới cảnh); cổng 4 cho phép chấp nhận nhưng luôn liệt kê |
| Tạo audio edge-tts rất chậm / `No audio was received` | Dịch vụ Microsoft chập chờn (có retry tới 15 lần/đoạn) | Chờ/tạo lại (đoạn đã xong được cache); hoặc dùng ElevenLabs |
| "Cần duyệt cổng … trước khi …" | Đúng thiết kế: chi phí/bước sau chỉ mở sau cổng trước | Duyệt cổng ở tab Tổng quan |
| Sửa nội dung xong thì mất duyệt | Đúng thiết kế (`bump_artifact`) | Duyệt lại; audio/timeline không đổi thì không phải làm lại |
| Cổng 5 báo `render_stale` / không xuất được | Dữ liệu (ảnh, chữ, giấy phép, chủ đề, nhạc…) đã đổi sau lần render final | Render lại bản cuối |
| Chữ tiếng Việt hiện dấu rời ("viê´t") | Font thiếu glyph xếp chồng (Georgia) | Dùng Times New Roman (đã là mặc định) |
| Khung `<video>` đen trong test headless | Chromium của Playwright không có H.264 | Edge/Chrome thật phát được; kiểm tra file bằng ffmpeg |
| Video âm thanh 96 kHz | loudnorm nâng tần số | Đã ép 48 kHz; QC cảnh báo nếu khác 48000 |
| Nhạc nền bị từ chối | đường dẫn không đầy đủ/không phải file âm thanh/dB ngoài -40…-6 | Dùng đường dẫn đầy đủ tới mp3/wav/m4a/ogg/flac ≤100 MB |
| Thử nghiệm ghi nhầm khóa vào `.env` thật | `PUT /settings/*` ghi `.env` theo cwd | Chạy backend thử nghiệm từ thư mục tạm (xem SETUP) |
| `tsc --noEmit` ở frontend "không kiểm tra gì" | dự án dùng project references | Dùng `npx tsc -b --noEmit` |
| Lỗi SQLite khi dọn thư mục tạm ở test (Windows) | race đóng file | Chạy lại 2–3 lần trước khi coi là hồi quy |

## Muốn xem chuyện gì xảy ra với một lần render
`GET /api/v1/documentary/projects/<id>/render/jobs/<job>/log` hoặc nút **Log** ở tab Render: có lệnh Remotion, tiến độ, lệnh ffmpeg và báo cáo QC theo mã cảnh.
