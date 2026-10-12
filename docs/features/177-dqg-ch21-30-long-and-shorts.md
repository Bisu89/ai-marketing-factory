# 177. Đại Quản Gia Là Ma Hoàng ch 21-30: 1 Long + 3 Short

Làm lại video cho chương 21-30 từ script `ep21..ep30/script.json` đã lưu (không viết lại lời kể): `long_21_30/` (146 beat, 12:04, 1920x1080, project 210 / job_268), `short_d/` (ch 21-24, 46.6s, project 206), `short_e/` (ch 25-27, 48.9s, project 207), `short_f/` (ch 28-30, 45.9s, project 208). Cả 4 Final QA 100.

Commit: "feat: manhua-series -- Dai Quan Gia ch21-30 Long + 3 Short".

Điểm cần biết:
- Ảnh chương 21-30 đã tải nhưng chưa cắt; chạy `recap.py cut` cho `dqgl_ep21..30` (panel số khớp script cũ, tối đa 71 khung/chương).
- Short chọn 10-13 beat/nhóm từ script từng tập (giữ nguyên lời); Long ghép toàn bộ, mỗi tập là một `section`.
- Script cũ dùng `type` `TURN`/`CLIMAX`/`COMMENTARY` mà API beat-plan từ chối (422); script mới đã đổi về BUILD/REVEAL.
- Khung chưa kiểm chứng bằng mắt: hình có thể lệch lời ở một số chỗ.
