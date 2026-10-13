# 184. Render output gọn (scenes xóa, tên video theo series, file text upload) + 10 Short best-of

**Cơ chế render** (`video_composer/service.py`, `core/output_naming.py`, `package_generate.py`):
- Video trong `job_<id>_<title>/output/` đặt tên `<title>.mp4` (tên truyện/series + hậu tố, không còn tiền tố `job_<id>_`). Thư mục output do người dùng chọn (có thể dùng chung) vẫn giữ `job_<id>_<title>.mp4` để job không đè nhau.
- Thư mục `scenes/` (clip chuyển động từng beat, ngang cỡ video) bị xóa ngay khi job `completed` (giữ khi debug hoặc khi job lỗi). Trước đây mỗi video chiếm gấp đôi dung lượng.
- Sau bước đóng gói sinh `<tên video>.txt`: TITLE, DESCRIPTION, HASHTAGS (có `#`), TAGS (YouTube) = hashtag bỏ `#`, cách nhau dấu phẩy để dán vào ô Tags. Tiêu đề lấy nguyên văn tiêu đề viết tay (`derive_title` của metadata.json xóa `?`, `|`).
- Giữ nguyên `thumbnail.jpg`, `metadata.json`, `render_metadata.json`, `qa_report.json`, `package.meta.json` trong output: trang Videos, bước QA và module đăng YouTube đọc chúng cạnh video, và chúng chỉ vài trăm KB.
- Test: `PlainVideoFilenameTests`, `PublishTextTests`; `test_pipeline_hardening` đổi tên file kỳ vọng và kiểm tra scenes đã bị xóa. Kiểm tra thật: 10 video xong, thư mục job chỉ còn `output/` (~8-11 MB mỗi Short).

**10 Short best-of** (`manhua-series/dai-quan-gia-la-ma-hoang/best_of/s01..s11`, chi tiết trong `BEST_OF_PLAN.md`): S01 ch1-2, S02 ch3-4, S03 ch5-6, S11 ch7-8, S05 ch24-27, S06 ch45-46, S07 ch67-69, S08 ch85-87, S09 ch92-94, S10 ch99-100; 39-51s, mỗi Short có 1-2 bình luận. S04 (ch 11-12) hoãn vì ảnh chương 11-20 hiện không còn trên đĩa; thay bằng S11 (ch 7-8). Tên nhân vật thống nhất: Ngưng Nhi, U Quỷ Thất.

Bug gặp: S09 lỗi giọng edge-tts ở mọi lần thử ("No audio was received") vì có beat bắt đầu bằng dấu chấm lửng ("... Trác đại ca!") và beat chỉ gồm "..." cuối câu; sửa bỏ chấm lửng rồi build lại (project 258); project 255 đổi tên "[FAILED...]".

Commit: "feat: render output cleanup (no scenes, series-named video, YouTube text sheet) + 10 best-of Shorts".
