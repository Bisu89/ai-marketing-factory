# 172 — Documentary: chủ đề "cinematic" + thư mục template Vox

**Vì sao:** người dùng thấy kiểu collage giấy cũ "lởm" và muốn phong cách tranh sơn dầu Baroque của kênh Biblical
Figures, kết hợp **ảnh tư liệu có ghi nguồn + ảnh AI** (không toàn bộ AI).

- **Chủ đề `cinematic`** (`remotion/src/cinematic.tsx`): ảnh tràn khung với chuyển động trôi chậm (hướng suy ra từ seed
  của cảnh, nên cùng cảnh luôn chuyển động giống nhau), vignette ấm, hạt phim; ảnh dọc → nền mờ + ảnh nguyên vẹn ở giữa
  (manifest có `imageAspect`); cảnh dữ liệu trên nền da tối viền vàng với chữ serif vàng/kem; phụ đề không hộp.
  Đủ 9 preset như collage. `theme` là tham số của mỗi lần render (`collage` | `cinematic`) và nằm trong manifest + hash,
  nên cùng dữ liệu khác chủ đề không bao giờ dùng lại video cũ. UI Render có ô chọn chủ đề (mặc định cinematic).
- **Template** `content-prompts/vox_documentary_template/`: `HANDOFF.md` (trạng thái, kiến trúc, bẫy, việc tiếp theo),
  `RULES.md`, `IMAGE_STYLE.md` (khối prompt Baroque lấy từ Biblical Figures, bỏ phần tôn giáo, `{ERA}`),
  `templates/` (spec trống, khung kịch bản, tiêu đề/mô tả), `checklists/`, `examples/constantinople_1453.spec.json`.
- **Công cụ dựng tập** `tools/episode_builder.py`: `create` (dự án + nguồn có trích đoạn **cắt nguyên văn** từ Wikipedia theo
  "needles" — không khớp thì dừng + khẳng định + kịch bản), `storyboard` (lập cảnh + áp `scene_overrides`), `images` (tải ảnh Commons
  kèm giấy phép/tác giả thật, nhập, gán; ảnh **luôn ở trạng thái chờ duyệt**, giấy phép CC BY-SA/GFDL/FAL bị cảnh báo), `status`.
  Công cụ **không duyệt cổng nào**; `tools/commons.py` tìm ảnh và đọc giấy phép.

Kiểm chứng: preview cinematic đủ độ dài của dự án thật (960×540, 118.5s, có tiếng, 0 khung đen) và xem 15 khung hình;
`episode_builder` chạy trọn create → (người duyệt) → storyboard → images trên backend tạm với DB riêng (12 khẳng định, 15 cảnh,
4 ảnh nhập, chạy lại không tạo trùng); test manifest cho `theme`, `imageAspect`, theme sai bị từ chối.
Bug bắt được: metadata Commons có trường kiểu số làm công cụ lỗi (`_plain` giờ chịu mọi kiểu).
Giới hạn: chưa render **bản cuối** cinematic cho dự án #1; prompt ảnh AI vẫn viết tay (xem `IMAGE_STYLE.md`); nhãn "Minh họa AI" chưa tự động.
Commit: "feat: documentary cinematic theme + Vox template folder and episode builder".
