# Manhua Recap — 1 chương truyện tranh → 1 video Short

Tool này dựng video bằng chính các khung tranh của truyện, dùng template `manhua_recap_vi`.
Nó cần backend đang chạy và gọi API của app.
Chạy tool bằng Python trong venv của backend.

```
cd backend
.venv\Scripts\python ..\tools\manhua_recap\recap.py fetch  https://manhuavn2.com/doc-truyen/van-co-chi-ton-chapter-2.html D:\truyen\chuong12
.venv\Scripts\python ..\tools\manhua_recap\recap.py cut    D:\truyen\chuong12
.venv\Scripts\python ..\tools\manhua_recap\recap.py script D:\truyen\chuong12 --seconds 50 --notes "lão già là chưởng môn"
.venv\Scripts\python ..\tools\manhua_recap\recap.py build  D:\truyen\chuong12
```

0. **fetch** (không bắt buộc): tải ảnh các trang của một chương trên manhuavn2.com vào thư mục.
   Chương VIP bị khóa thì tool sẽ báo và không tải. Với trang web khác, bạn tự tải ảnh bằng extension trình duyệt.
1. **cut**: ghép các trang (jpg/png/webp, xếp theo tên file) thành một dải dài, rồi cắt ở các khe màu trơn giữa hai khung.
   Kết quả nằm trong `chuong12/_recap/panels/p001.jpg…`, kèm ảnh xem nhanh `panels_preview.jpg`.
   Xoá khung rác (trang bìa, credit, quảng cáo) trước khi sang bước tiếp theo.
   Khung cao hơn 2 lần chiều rộng (các khung dính nhau vì không có khe trắng) được tự cắt thêm ở chỗ ít chi tiết nhất.
2. **script**: AI xem các khung, đọc cả bong bóng thoại, rồi chọn khung và viết lời kể nhanh. Kết quả ghi vào `_recap/script.json`.
   Có thể sửa tay tiêu đề, lời kể hoặc tên khung trong file này.
   Nên dùng `--notes` để ghi tên truyện và tên nhân vật chính, AI sẽ gọi tên đúng hơn.
3. **build**: đưa các khung vào Asset Library, tạo project và bắt đầu render.
   Thêm `--no-render` nếu chỉ muốn tạo project, chưa render.

Lưu ý: tranh là tác phẩm của người khác, nên YouTube có thể đánh "reused content" hoặc nhận claim bản quyền.
Kênh dùng ảnh AI (template `manhua_ai_vi`, tạo bằng nút "Generate Full by AI") không có rủi ro này.
