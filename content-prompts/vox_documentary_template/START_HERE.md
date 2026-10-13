# START HERE — đọc file này đầu tiên khi mở session mới (cập nhật 2026-10-13)

Thứ tự đọc (đủ để làm tiếp mà không phải hỏi lại):
1. File này.
2. `content-prompts/vox_documentary_template/HANDOFF.md` — hệ thống Vox (backend + Remotion), 5 cổng duyệt, bẫy đã gặp.
3. `content-prompts/vox_documentary_template/RULES.md` — luật sản xuất; **mục 8 = phong cách chuẩn: theme `collage` + ảnh kiểu poster**.
4. `biblical-figures-prompts/vox/HANDOFF.md` — series Biblical Figures tập 6–8 (dự án #2, #4, #5) và cách làm tập 9.
5. `content-prompts/literature_vi/` (`CHANNEL.md`, `VISUAL.md`, `SCRIPT_TEMPLATE.md`, `MAPPING.md`) — kênh văn học Việt (Chí Phèo, Lão Hạc).

## Quy ước làm việc với chủ kênh
- Trả lời tiếng Việt. Không tự đổi phong cách chốt (collage + poster); `cinematic`/`poster` đã bỏ khỏi UI.
- Cổng duyệt: chủ kênh đã cho phép AI duyệt cổng 1–4 khi chủ kênh yêu cầu chạy tiếp; **cổng 5 (duyệt cuối) luôn là của chủ kênh**. Không tự đăng.
- Không gọi API trả phí; ảnh do chủ kênh tạo từ CSV (ChatGPT). Giọng `edge_en` (tiếng Anh) hoặc `edge` (tiếng Việt), miễn phí.
- Commit/push khi xong việc (đã được cho phép). `git fetch` trước (có session khác làm manhua/literature).
- **Không sửa file trong `backend/` khi đang render** (uvicorn `--reload` sẽ ngắt job). Preview thử chỉ 30–70 giây.
- Mọi trích dẫn nguồn phải cắt nguyên văn bằng `episode_builder.py`; không bịa nguồn/năm.

## Việc đang dở
| Việc | Trạng thái |
|---|---|
| Biblical Figures tập 7 (#4) và tập 8 (#5) | Đã render bản collage + ảnh poster; **chờ chủ kênh duyệt cổng 5** (tập 8 cần duyệt lại) |
| Biblical Figures tập 9 (Thomas) | Chưa viết; chưa có ảnh |
| Chí Phèo tập 1 (dự án #3) | Kịch bản 36 đoạn ~1.350 từ đã vào app (cổng 1–2 duyệt); **chờ chủ kênh chốt kịch bản**, rồi 24 ảnh theo `content-prompts/literature_vi/episodes/chi-pheo-ep01/image_prompts.csv` (đừng tạo ảnh trước khi kịch bản chốt vì mã cảnh có thể đổi) |
| Phần bình luận của kênh văn học | Là bản nháp AI; chủ kênh viết lại |
| Việc kỹ thuật nhỏ | Thẻ bản đồ còn trống (không có dữ liệu địa lý); kiểm thử dấu tiếng Việt của chữ cắt dán; SFX; đóng gói PyInstaller (remotion + faster-whisper) |

## Dữ liệu ngoài git (phải có trên máy)
Ảnh poster (`biblical-figures-prompts/vox/ep7_posters|ep8_posters|poster_test|pool_recovered`), video render và DB app (`backend/data/`). Nếu sang máy khác: xem mục "Tạo lại ở máy khác" trong `biblical-figures-prompts/vox/HANDOFF.md`.

Gói tài liệu/spec/mã Remotion để mang đi: `exports/vox-template-2026-10-13.zip` (không chứa ảnh/video).
