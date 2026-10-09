# 169 — Documentary: render (Phase 5)

Remotion vẽ hình, ffmpeg ghép tiếng, ffprobe + quét khung hình đen kiểm tra.
Hướng thiết kế (lấy ý tưởng từ `vox-director`, chỉ dùng thứ miễn phí): collage giấy
**dựng bằng code trên ảnh thật/ảnh tạo tay**, không dùng AI vẽ poster hay AI video
→ không tốn API, và chữ trên màn hình luôn đúng chính tả (không nhúng trong ảnh).

- **Giao diện collage** (`remotion/src/theme.ts`, `collage.tsx`): nền giấy có texture,
  mép giấy rách (đa giác sinh theo seed ⇒ cùng seed cùng hình), băng keo, halftone,
  highlight vàng, vòng đỏ vẽ dần. Font hệ thống (Impact/Arial/Times New Roman) nên
  không cần mạng hay giấy phép; Georgia bị loại vì thiếu glyph tiếng Việt xếp chồng.
- **9 preset** (`presets.tsx`): PhotoKenBurns, ArchivalPortrait, NewspaperStack, MapZoom,
  TimelineBuild, BigNumber, EvidenceBoard, HeadlineImpact, SplitComparison — đủ mọi
  preset planner có thể sinh. MapZoom không có dữ liệu địa lý nên chỉ vẽ nền đường
  đồng mức *trang trí* + ghim + nhãn (không tuyên bố vị trí); nếu bạn nhập ảnh bản
  đồ thì zoom vào ảnh đó. NewspaperStack dùng thanh xám thay cho thân bài (không bịa chữ).
- **Manifest** (`render_plan.py`): mọi thời điểm là *frame* suy từ timeline thật; cảnh
  nối liền (không hở/chồng); mỗi cảnh fade-in đè lên cảnh trước nên không thể lộ khung
  đen. Chữ trên màn hình = phần bạn nhập ở Storyboard, nếu không thì **suy ra từ chính
  lời dẫn** (năm, con số, câu, tên riêng) và được cue đúng lúc từ đó được đọc.
  Preset dữ liệu mà không có gì để hiện (timeline không có năm…) tự chuyển sang
  HeadlineImpact thay vì vẽ khung rỗng.
- **Hash đầu vào** (manifest + audio master + mã nguồn Remotion + tham số): yêu cầu
  trùng ⇒ dùng lại video đã render, không render lại.
- **Job nền** (`render.py`): 1 render/lần, tiến độ đọc từ Remotion, hủy được, log lưu
  file; job treo sau khi app khởi động lại bị đánh dấu lỗi. **Không có resume giữa
  chừng** — chạy lại thì render lại từ đầu (phần rẻ như chép ảnh, dựng manifest được tính lại).
- **Preview**: chọn 15/30/60 giây đầu hoặc toàn bộ, kích thước 25–75%. **Bản cuối** luôn
  1920×1080, 30 fps, đủ độ dài, chuẩn hóa âm lượng (loudnorm) tùy chọn, phụ đề ghi
  lên hình tùy chọn.
- **Kiểm tra chất lượng**: độ phân giải, fps, có luồng tiếng, thời lượng, video không
  ngắn hơn narration, và khung hình đen — mỗi lỗi nêu **mã cảnh** chịu trách nhiệm.
  Cảnh timing "ước lượng" thành cảnh báo. Render không tự động coi là đạt/duyệt.
- **Cổng 5**: cần đã duyệt cổng 4 để render; duyệt "final" cần một bản final thành công
  đạt QC *và còn khớp dữ liệu hiện tại* (đổi gì sau khi render ⇒ `render_stale`). Một bản
  final mới thu hồi duyệt cũ.
- Endpoint video tự phục vụ HTTP Range (Starlette 0.38 chưa có) để tua được.
- UI: tab **Render** (điều kiện, preview/final, tiến độ, hủy, trình phát, log, kết quả QC
  theo cảnh). Migration `0014_documentary_render` (up/down/up).

Kiểm chứng thật: Remotion + ffmpeg trên máy này — preview 15s ở 480×270 có tiếng, 0 khung
đen; bản cuối **1920×1080 H.264 + AAC, 43.63s, 0 lỗi QC**; yêu cầu preview lặp lại dùng
cache, video trả Range 206; duyệt cổng 5 → "Đã duyệt" qua trình duyệt headless
(Playwright) đi trọn từ tạo dự án. 166 test documentary pass (gồm một test render Remotion
thật và QC bằng ffmpeg thật).
Bug bắt được khi xem khung hình thật: font Georgia vỡ dấu tiếng Việt (ế, ằ) → Times New
Roman; highlight chỉ phủ dòng đầu khi tiêu đề xuống dòng; nhãn đè lên phụ đề; EvidenceBoard
1 thẻ nằm lệch; TimelineBuild rỗng khi không có năm; trình phát không tự bật video vừa
render xong; heuristic tên riêng coi chữ thường có dấu là chữ hoa (khoảng `À-Ỹ`); và bài
kiểm thử giao diện từng ghi key ElevenLabs giả vào `backend/.env` thật (đã xóa — chạy
kiểm thử với backend từ thư mục tạm).
Giới hạn: chưa có nhạc nền/SFX, chưa có export (manifest + xuất file) — Phase 6; Chromium
của Playwright không giải mã H.264 nên khung phát hiện đen trong test headless (Edge/Chrome
thật thì phát được; hình ảnh đã kiểm tra trực tiếp từ file MP4); font phụ thuộc máy có
Impact/Arial/Times New Roman; bản đóng gói PyInstaller chưa gồm thư mục `remotion/`.
Commit: "feat: documentary Remotion collage presets, render jobs, QC and render tab".
