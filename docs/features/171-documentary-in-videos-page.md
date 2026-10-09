# 171 — Documentary final renders show up on the Videos page

Trang **Videos** chỉ đọc bảng render của Video Factory/Composer (`VideoComposeJob`), còn render
của phim tài liệu nằm ở `documentary_render_job` nên video hoàn tất không xuất hiện ở đó.

- `GET /produced-videos` (composition root) gộp thêm các **render final** của documentary:
  chỉ bản thành công mới nhất của mỗi dự án (bản cũ bị thay thế không liệt kê), không liệt kê
  preview; bản lỗi chỉ hiện ở bộ lọc "Lỗi/Tất cả". Mỗi mục có `source` ("factory" |
  "documentary") vì `render_job_id` là id của bảng nguồn tương ứng.
- Ảnh bìa `thumbnail.jpg` cạnh video (cùng quy ước của trang Videos) được tạo sau khi final
  render thành công, và tạo bù khi liệt kê nếu thiếu (video render từ trước).
- `POST /produced-videos/documentary/{job_id}/open-folder` (đường dẫn lấy từ DB).
- Giao diện: nhãn "Phim tài liệu · …" trên thẻ, nút "Mở trong Phim tài liệu", mở thư mục
  đúng nguồn, key React gồm cả `source`; video ngang hiển thị nguyên khung (thẻ vốn là khung dọc).

Kiểm chứng: 4 test mới + 6 test cũ của `test_produced_videos` (đã bổ sung bảng documentary vào
setup); xem trang thật bằng Playwright: thẻ, ảnh bìa, chi tiết 1920×1080 / 95.0 MB, URL video và
ảnh bìa trả 200.
Commit: "feat: list documentary final renders on the Videos page".
