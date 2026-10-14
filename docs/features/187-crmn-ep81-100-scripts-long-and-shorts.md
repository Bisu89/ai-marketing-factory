# 187. Chàng Rể Mạnh Nhất Lịch Sử tập 81-100: script, 2 Long, 8 Short

Tập 81-100 chưa có script nào; tôi đọc ảnh từng tập (cắt lại `crmn_ep81..100`) rồi viết `ep81..ep100/script.json` (25-67 beat/tập, 1-4 bình luận). Số `pNNN` là **khung của `cut`**.

| Video | Tập | Độ dài | Project / job |
|---|---|---|---|
| Long 09 | 81-90 | 15:38 | 263 / 325 |
| Long 10 | 91-100 | 17:15 | 264 / 326 |
| Short B01-B08 | 81 / 82-83 / 85-86 / 87 / 91 / 92-93 / 97 / 94 | 38-47s | 265-272 |

- Long chọn ~18 beat/tập từ script tập (đều nhau + giữ bình luận). Short = 1-2 tập, ~230-270 từ, hook viết mới.
- Tập 99: đoạn tán tỉnh trên xe ngựa bị lược các câu gợi ý để an toàn kiếm tiền.
- Render chạy trên backend phụ cổng 8010 (backend 8000 bị lỗi 403 giọng edge-tts, xem 186); `MANHUA_API=http://127.0.0.1:8010/api/v1` cho `recap.py`.
- `STORY.md` thêm Long 09-10.
- Khung ảnh Long/Short chưa đối chiếu lại bằng mắt sau khi chọn beat (script từng tập đã viết khi xem ảnh).

Commit: "feat: manhua-series -- Chang Re ep81-100 scripts, Long 09-10 + 8 Shorts".
