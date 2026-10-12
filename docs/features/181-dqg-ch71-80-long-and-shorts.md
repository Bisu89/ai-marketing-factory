# 181. Đại Quản Gia Là Ma Hoàng ch 71-80

Từ `ep71..ep80/script.json`. Short S/T/U (ch 71-74 / 75-77 / 78-80, project 230-232, job 288/287/289) và hai Long chia đôi: ch 71-75 (7:25, project 233 / job 290), ch 76-80 (11:21, project 234 / job 291). Final QA 100 cả 5, không phải retry. `STORY.md` đã thêm 2 Long.

Commit: "feat: manhua-series -- Dai Quan Gia ch71-80".

- Script ep71-80 đánh số theo **trang ảnh gốc**, nhưng trang có hai dạng: ep72/74/75/78 trang đã là khung nhỏ (750x586) nên copy thẳng thành `_recap/panels/pNNN.jpg` (bản cắt cũ để ở `panels_cut`); ep71/73/76/77/79/80 trang là dải dài (vd 700x2000) nên ánh xạ trang -> khung đầu tiên của trang đó qua `_recap/panel_pages.json`. Xác nhận bằng mắt: trang cuối ep80 (luồng sáng xanh) và ep76 ("Cái gì?") khớp beat cuối.
- Sau khi render xong, thư mục `backend/data/library/_video_composer` chỉ còn job 290 và 291; các job cũ hơn (kể cả 3 Short này) không còn trên đĩa (không do code build/render xóa; cần xác nhận ai/cái gì dọn). Project và factory-run trong DB vẫn còn, render lại được.
