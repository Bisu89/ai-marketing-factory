# 165 — Documentary: storyboard & assets (Phase 3)

Kịch bản đã duyệt → các cảnh có ID ổn định → kho asset → vòng tạo ảnh thủ
công qua CSV (không gọi API sinh ảnh, không tốn tiền). Cổng 3
(`storyboard_assets`) kiểm tra nội dung thật.

- **Storyboard** (`storyboard.py`): cắt theo ranh giới câu/đoạn (18–45 từ/cảnh,
  cấu hình trong `StoryboardPolicy`), không cắt theo giây cố định; câu chuyển
  đoạn ngắn được gộp vào đoạn sau. Cần cổng `script` đã duyệt mới lập được.
- **Bậc thang chi phí** (rule-based, giải thích được): timeline/năm →
  `TimelineBuild`, số liệu → `BigNumber`, địa điểm → `MapZoom`, phần bằng chứng
  → `EvidenceBoard`, bước ngoặt ngắn → `HeadlineImpact` — đều là đồ họa lập
  trình, **không cần ảnh**. Còn lại là ảnh; các cảnh liền nhau trong cùng một
  đoạn **dùng chung một ảnh** (tối đa 3 cảnh/ảnh). Video AI không bao giờ được
  chọn (`allow_ai_video=False`).
- **Lập lại storyboard không phá hỏng**: cảnh có lời dẫn không đổi giữ nguyên
  dòng, `scene_key`, ảnh đã gán và chỉnh sửa tay; `scene_key` không bao giờ
  được cấp lại. Sửa một đoạn chỉ tạo cảnh mới cho đoạn đó.
- **Kho asset** (`assets.py`): nhập file (png/jpg/webp, ≤25 MB, Pillow xác
  thực, chống trùng theo sha256), tên file lưu do hệ thống sinh (không bao giờ
  dùng tên người dùng nhập). Ảnh `archival` phải có license (khác "unknown") và
  attribution mới duyệt được; sửa metadata thì quay về `pending`.
- **Vòng CSV**: `GET .../images/export-csv` xuất đúng cột của quy trình
  zombie/biblical (STT, Ten file, Tags, Prompt đầy đủ; UTF-8 BOM) cho **chỉ**
  những nhóm ảnh còn thiếu/bị từ chối/cũ; ảnh đã duyệt có cùng `input_hash`
  được tái dùng và không có trong CSV. Bạn tạo ảnh, đặt tên bắt đầu bằng
  `S001...`, rồi `POST .../images/import-folder` khớp theo `scene_key`.
- **Cổng 3**: mọi cảnh phải là đồ họa lập trình hoặc có ảnh đã duyệt, file còn
  trên đĩa, ảnh không cũ. Thay/duyệt/từ chối ảnh sau khi duyệt cổng sẽ làm
  cổng đó mất hiệu lực (bump `storyboard`).
- Migration `0011_documentary_storyboard_assets` (up/down/up chạy trên DB tạm).

Kiểm chứng: 75 test documentary pass 2 lần; luồng HTTP (plan → CSV → nhập
thư mục → duyệt asset → duyệt cổng 3 → CSV lần 2 trống). Lỗi đường dẫn người
dùng trả 400 (không phải 500).
Bug bắt được: (1) cùng một file gán cho hai nhóm bị báo "ảnh cũ" sai — vì cờ
stale gắn vào asset; chuyển sang `assigned_hash` trên cảnh. (2) sửa lời mô tả
của cảnh con làm nó không bao giờ vào CSV — giờ tách ra thành nhóm riêng.
Giới hạn: chưa có giao diện; preset chỉ được *chọn*, chưa được render
(Phase 5); độ dài cảnh vẫn là ước tính cho tới khi có audio.
Commit: "feat: documentary storyboard + asset registry + manual image CSV loop".
