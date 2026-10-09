# Vox Documentary Template — làm một tập mới

Template cho phim tài liệu lịch sử 8–10 phút kiểu Vox. **Đọc `HANDOFF.md` trước** (trạng thái, kiến trúc, bẫy đã gặp), rồi
`RULES.md` và `IMAGE_STYLE.md`.

```
vox_documentary_template/
  HANDOFF.md            trạng thái + kiến trúc + việc tiếp theo (đọc đầu tiên)
  RULES.md              quy tắc sản xuất (nguồn, kịch bản, ảnh, giọng, render, đăng)
  IMAGE_STYLE.md        khối prompt ảnh AI Baroque + chiến lược kết hợp ảnh tư liệu
  templates/
    spec_template.json  khung spec trống cho một tập
    script_template.md  khung kịch bản 7 phần (để soạn trước khi đưa vào spec)
    title_description_template.txt   khung tiêu đề/mô tả/ghi công khi đăng
  checklists/
    episode_checklist.md  danh sách việc theo từng cổng
    qc_checklist.md       soát cuối bằng tay (nghe/xem) trước cổng 5
  examples/
    constantinople_1453.spec.json   tập mẫu đã chạy thật (12 khẳng định, 15 cảnh, 5 ảnh)
  tools/
    episode_builder.py    dựng tập từ spec: create | storyboard | images | status
    commons.py            tìm ảnh trên Wikimedia Commons + đọc giấy phép/tác giả thật
```

## Làm một tập mới (10 bước)

1. **Chọn chủ đề** và đọc nguồn thật (Wikipedia + sách/tài liệu). Chép `templates/spec_template.json` thành
   `episodes/<ten_tap>/spec.json` (thư mục `episodes/` do bạn tạo; thêm `.cache/` và `*.state.json` vào .gitignore nếu muốn).
2. **Điền `sources` + `claims`**: `needles` là cụm từ *có thật trong bài* để cắt trích đoạn nguyên văn. Con số tranh cãi ⇒ `disputed` + `note`.
3. **Soạn kịch bản** theo `templates/script_template.md` rồi đưa vào `script` (mỗi đoạn gắn `claims`). Viết số bằng chữ số, năm 4 chữ số.
4. **Chạy backend từ thư mục tạm nếu thử nghiệm** (xem HANDOFF mục 6). App thật: cổng 8000.
5. `python tools/episode_builder.py create episodes/<ten_tap>/spec.json` → tạo dự án + nguồn + khẳng định + kịch bản nháp.
6. **Trong app (Phim tài liệu → dự án):** duyệt **cổng 1**, chuyển bước, duyệt **cổng 2**, chuyển tới `storyboard_review`.
7. `python tools/episode_builder.py storyboard episodes/<ten_tap>/spec.json` → lập cảnh; chỉnh `scene_overrides` (preset, chữ trên màn hình, mô tả ảnh) rồi chạy lại.
8. **Ảnh:** điền `images` (Commons: `python tools/commons.py "truy vấn"` để tìm) → `episode_builder.py images ...`; cảnh còn thiếu ảnh ⇒ tab Ảnh → xuất CSV
   → tạo ảnh AI theo `IMAGE_STYLE.md` → nhập thư mục. **Tự đọc giấy phép từng ảnh rồi duyệt** → duyệt **cổng 3**.
9. Tab **Giọng đọc & Timeline**: chia đoạn → ước tính → tạo audio (edge miễn phí) → ghép master → **nghe lại** → căn chỉnh → duyệt **cổng 4**.
10. Tab **Render**: preview (chủ đề điện ảnh) → xem → bản cuối → soát `checklists/qc_checklist.md` → duyệt **cổng 5**. Lấy file ở trang **Videos**.

Công cụ **không duyệt thay bạn** ở bất kỳ cổng nào, và không tự đăng.

## Lệnh nhanh
```
python tools/commons.py "Fall of Constantinople painting" "Mehmed II portrait"      # tìm ảnh + xem giấy phép
python tools/episode_builder.py status episodes/<ten_tap>/spec.json                 # xem dự án đang ở bước nào
DOC_API=http://127.0.0.1:8000/api/v1/documentary python tools/episode_builder.py ...   # chọn backend
```
