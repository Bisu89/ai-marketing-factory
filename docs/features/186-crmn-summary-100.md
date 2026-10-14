# 186. Chàng Rể Mạnh Nhất Lịch Sử: tóm tắt tập 1-100

`manhua-series/chang-re-manh-nhat-lich-su/summary_100/` (+ `summary_100_narration.md`): project 262 / job 316, 9:31, 1920x1080, Final QA 100. 115 beat, ~2.880 từ, 6 câu bình luận, 12 mục (mở đầu, 10 phần, kết).

- **Tập 81-100 chưa có script**: tôi đọc ảnh các tập này (cắt lại `crmn_ep81..100`) rồi tự tóm tắt, nên phần 9-10 chỉ mức tóm tắt, một số chi tiết ở tập 97-100 là suy luận từ ảnh.
- **Khung ảnh**: tập 1-80 ghép câu với khung của script cũ bằng so khớp từ khóa (IDF), không xem từng khung; tập 81-100 chọn khung theo từ khóa tên nhân vật/sự kiện -> số tập. Một số khung chỉ gần đúng cảnh.
- **Lỗi gặp khi render**: 5 lần retry liên tiếp fail GENERATING_VOICE với 403 từ `speech.platform.bing.com` dù tự gọi `edge_tts` (cả `WordBoundary`) cho cả 115 câu đều chạy. Nguyên nhân nằm ở tiến trình backend đang chạy lâu (cổng 8000, không dừng được từ phiên này); chạy backend thứ hai trên cổng 8010 (cùng dữ liệu) rồi retry là qua ngay. Một lần fail khác là do bấm retry 2 lần liền khiến hai lượt tạo giọng chạy chồng (`seg_000.mp3` bị xóa) -- chỉ bấm retry một lần mỗi lượt.
- Ngoài ra: `render-cache auto-sweep` của backend tự xóa vài trăm MB cache khi khởi động (thấy ở log 8010).

Commit: "feat: manhua-series -- Chang Re Manh Nhat Lich Su 100-episode summary".
