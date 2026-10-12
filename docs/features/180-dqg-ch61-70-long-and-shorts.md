# 180. Đại Quản Gia Là Ma Hoàng ch 61-70

Từ `ep61..ep70/script.json`. Short P/Q/R (ch 61-63 / 64-67 / 68-70: 47.1s / 48.3s / 47.3s, job 282/284/283) và hai Long chia đôi ngay từ đầu (vì Long 51-60 một khối từng fail giọng): ch 61-65 (11:22, job 286), ch 66-70 (9:50, job 285). Final QA 100, không phải retry. `STORY.md` đã thêm 2 Long.

Commit: "feat: manhua-series -- Dai Quan Gia ch61-70".

- ep68 và ep69: script đánh số theo **trang ảnh gốc** (trang đã là khung 750x586), không theo khung của `cut` (cut gộp 70 trang thành 46 khung nên số lệch/vượt). Đã dựng lại `_recap/panels` của hai chương này bằng cách copy trang gốc thành `pNNN.jpg` (bản cắt cũ để ở `panels_cut`). Xác nhận bằng mắt: trang 68 là câu "Ta đã lừa các ngươi".
- Khung các chương còn lại chưa kiểm chứng bằng mắt.
