# 168 — Documentary: giao diện (Phase 1–4)

Trang `/documentary` (menu "Phim tài liệu") và `/documentary/:id` điều khiển
toàn bộ luồng đã có ở backend (features 163–167). Giao diện tiếng Việt; mọi
quy tắc vẫn do backend ép buộc — UI chỉ hiển thị lỗi/blocker của backend.

- **Danh sách + tạo dự án** (ngân sách tùy chọn), nút "Dự án mẫu" (gắn nhãn MẪU).
- **Tổng quan**: bước hiện tại, thanh các cổng duyệt, nút sang bước tiếp (khóa
  khi còn cổng chưa duyệt), hộp kiểm tra trước khi duyệt, Duyệt/Từ chối (có
  xác nhận), quay lại bước trước (xác nhận vì thu hồi duyệt), lịch sử duyệt.
- **Nghiên cứu**: nguồn + khẳng định (nút lưu khóa khi trạng thái cần nguồn mà
  chưa chọn nguồn; URL sai hiện lỗi từ backend).
- **Kịch bản**: dàn ý → kịch bản (mock/llm; `llm` hỏi xác nhận vì tốn token), sửa
  từng đoạn, gắn khẳng định, lưu thành phiên bản mới, khôi phục phiên bản cũ.
- **Storyboard**: bảng cảnh, sửa preset/prompt/chữ trên màn hình/ghi chú.
- **Ảnh** (contact sheet): xuất danh sách cần tạo + tải CSV, nhập thư mục ảnh đã
  tạo, duyệt/từ chối từng ảnh, thay/gán ảnh khác, nhập ảnh tư liệu kèm
  giấy phép/ghi công, ảnh lỗi thời được cảnh báo.
- **Giọng đọc & Timeline**: chọn backend, ước tính chi phí, xác nhận trước khi
  chạy backend trả phí/vượt ngân sách, nghe từng đoạn và master, căn chỉnh,
  bảng timing (nguồn timing, % khớp từ, cảnh "ƯỚC LƯỢNG" gắn cờ), chỉnh tay ranh
  giới cảnh, phụ đề + tải SRT, kết quả kiểm tra cổng 4.
- **Cài đặt giọng**: cấu hình ElevenLabs; API key chỉ gửi đi, không bao giờ hiện lại.
- Backend thêm `GET /documentary/projects/{id}/assets/{asset_id}/file` (phục vụ
  ảnh contact sheet; đường dẫn lấy từ DB, không từ request).
- Chưa có tab render/duyệt video cuối/xuất file — chưa có backend (Phase 5).

Kiểm chứng: `npx tsc -b --noEmit` sạch, `npm run build` OK; chạy thật bằng
Playwright (Chromium headless) trên backend + DB tạm: tạo dự án → nhập nguồn/
khẳng định → kịch bản → duyệt 2 cổng → storyboard → CSV → nhập 5 ảnh → duyệt
ảnh → cổng 3 → tạo audio (cache lần 2) → master → căn chỉnh → cổng 4 → lưu cấu
hình ElevenLabs; key không xuất hiện trong DOM. Chưa thử trên Firefox/Safari,
chưa thử với `llm`/ElevenLabs thật.
Bug bắt được khi chạy trình duyệt thật: (1) hook tải dữ liệu bật "Đang tải…"
mỗi lần dự án cập nhật khiến cả tab bị gỡ/dựng lại (nút biến mất giữa lúc bấm,
form đang mở bị đóng) → giữ dữ liệu cũ khi tải lại; (2) CSS toàn cục của repo:
`.btn-danger` (StudioPage.css) và `.btn-sm` (DashboardPage.css) đè lên class
cùng tên → nút "Từ chối" thành khối đỏ trống chữ → đổi sang `doc-btn-*`.
Commit: "feat: documentary UI for research, script, storyboard, assets, narration and timeline".
