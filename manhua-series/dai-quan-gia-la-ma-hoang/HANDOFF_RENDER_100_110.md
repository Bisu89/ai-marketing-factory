# Handoff: render Long 100-110 + 3 Short (Đại Quản Gia Là Ma Hoàng)

Kịch bản đã viết xong và đã push (commit `194c886`). Việc còn lại là **build + render + QA**, rồi ghi kết quả vào `SERIES.md`.

## 4 video cần render

| Video | Script | Chương | Chế độ | Beat |
|---|---|---|---|---|
| Long | `long_100_110/script.json` | 100-110 | 16:9 (`manhua_recap_long_vi`) | 240, ~5600 từ |
| Short AB | `short_ab/script.json` | 101-103 | 9:16 | 14 |
| Short AC | `short_ac/script.json` | 104-107 | 9:16 | 14 |
| Short AD | `short_ad/script.json` | 108-110 | 9:16 | 14 |

Template tự chọn theo trường `template` trong script (Long có, Short không). Không cần cắt lại ảnh: panel của `dqgl_ep100`..`dqgl_ep110` đã `cut` sẵn trong `manhua-recap/` và đã kiểm tra đủ file.

## Lệnh (chạy từ `backend`, backend đang chạy cổng 8000)

```
cd backend
# Long (panel của nhiều chương, script dùng dạng dqgl_epNNN/pNNN.jpg)
.venv\Scripts\python ..\tools\manhua_recap\recap.py build ..\manhua-recap\dqgl_ep100 --script ..\manhua-series\dai-quan-gia-la-ma-hoang\long_100_110\script.json --name "Dai Quan Gia - Long 100-110"
# 3 Short
.venv\Scripts\python ..\tools\manhua_recap\recap.py build ..\manhua-recap\dqgl_ep101 --script ..\manhua-series\dai-quan-gia-la-ma-hoang\short_ab\script.json --name "Dai Quan Gia - Short AB 101-103"
.venv\Scripts\python ..\tools\manhua_recap\recap.py build ..\manhua-recap\dqgl_ep104 --script ..\manhua-series\dai-quan-gia-la-ma-hoang\short_ac\script.json --name "Dai Quan Gia - Short AC 104-107"
.venv\Scripts\python ..\tools\manhua_recap\recap.py build ..\manhua-recap\dqgl_ep108 --script ..\manhua-series\dai-quan-gia-la-ma-hoang\short_ad\script.json --name "Dai Quan Gia - Short AD 108-110"
```

Thư mục chương đứng sau `build` chỉ là điểm neo; panel thật lấy theo tiền tố `dqgl_epNNN/` trong từng beat.

## Việc phải làm sau khi build

1. Factory-run dừng ở `NEEDS_REVIEW` là bình thường với mọi project manhua. Tiếp tục bằng `POST /factory-runs/{run_id}/continue?force=true` (`force` là query param, không phải body).
2. Voice edge-tts hay chập chờn ("No audio was received", `TTS_GENERATION_FAILED`). Chạy tuần tự từng video, đừng render song song. Nếu fail, tạo factory-run mới rồi thử lại.
   Long có 240 beat, rủi ro cao nhất (ghi chú ở `SERIES.md` ngày 2026-09-30: bản 174 beat fail 16 lần). Nếu fail liên tục thì tách đôi theo `section`: tập 100-105 và 106-110, mỗi nửa một project (script `long_100_110` chỉ có 11 `section`, cắt tại ranh giới tập).
3. Chấm QA (Final QA) và ghi: project, job, thời lượng, điểm.
4. In mục lục thời gian cho Long: `recap.py timestamps <project_id> --script ..\manhua-series\dai-quan-gia-la-ma-hoang\long_100_110\script.json`.
5. Xem video thật, đối chiếu hình với lời kể. Nếu lệch, chỉ sửa `script.json` rồi build lại (project mới).
6. Ghi một dòng vào mục "Nhật ký" của `SERIES.md` (project/job/QA/thời lượng/mục lục), rồi commit và push.

## Những điều không được làm

- **Đừng dùng** `ep102`, `ep104`-`ep110` (và `ep111`+ nếu có): bản OpenAI lệch truyện (ch104 chép nhầm cảnh ch105, thiếu bẫy Tề gia, thiếu việc giả danh Tống Ngọc). Chỉ `ep100`, `ep101`, `ep103` đúng.
- Không sửa lời kể trong 4 script này mà không đối chiếu ảnh trong `manhua-recap/dqgl_epNNN/_recap/sheets/`.
- Tên nhân vật đang dùng: chị Tống Thiến, em Tống Ngọc (Tiểu Ngọc), Đồng Thiên Bá, em gái Đồng Hiểu Uyển, Tề Cường Liệt, Tề Thiên Lôi. Chưa chắc: "Tống Thiến" có thể là "Tống Thiên" ở vài trang.
- Chương 102: cô gái tóc tím và người đồng hành cố ý không gọi tên (chưa xác nhận).

## Sau khi Long đã xong

Memory của dự án yêu cầu: thêm Long mới vào `STORY.md`. Việc này đã làm (`long_100_110` đã có trong `LONGS` của `build_story.py`), chỉ cần chạy lại `python build_story.py` nếu sửa lời kể.
