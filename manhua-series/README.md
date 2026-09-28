# Manhua Series: kịch bản Claude tự viết

Thư mục này lưu **kịch bản và ghi chú** của các series recap truyện tranh, và được đưa lên git.
Ở công ty hay ở nhà chỉ cần `git pull` là có đủ.

Kịch bản trong đây do **Claude tự đọc tranh và viết tay**, không gọi OpenAI, nên **không tốn phí API**.
Nó chỉ dùng hạn mức gói Claude của phiên chat.

## Cấu trúc

```
manhua-series/
  README.md                        <- file này: quy trình + cách setup máy mới
  <ten-truyen>/
    SERIES.md                      <- hồ sơ truyện, nhân vật, kế hoạch tập, trạng thái
    ep01/script.json               <- kịch bản tập 1 (panel + lời kể + loại beat)
    ep02/script.json
    ...
```

**Ảnh tranh KHÔNG nằm ở đây** (quá nặng, và đã bị git bỏ qua).
Ảnh nằm ở `manhua-recap/<thư mục chương>/`.
Mỗi `script.json` có trường `source_dir` cho biết nó lấy khung từ thư mục nào.

## Quy trình làm một tập

Chạy từ thư mục `backend`, với backend đang chạy ở cổng 8000.

```
cd backend
# 1. Tải ảnh chương (manhuavn2.com; chương trên máy chủ ảnh chặn tải thì tải tay bằng extension trình duyệt)
.venv\Scripts\python ..\tools\manhua_recap\recap.py fetch <link-chương> ..\manhua-recap\<thư mục>
# 2. Cắt thành từng khung
.venv\Scripts\python ..\tools\manhua_recap\recap.py cut    ..\manhua-recap\<thư mục>
# 3. Tạo ảnh đọc (6 khung/ảnh, có tên khung) để Claude đọc
.venv\Scripts\python ..\tools\manhua_recap\recap.py sheets ..\manhua-recap\<thư mục>
# 4. Nhờ Claude: "đọc sheets của <thư mục> và viết ep0N/script.json"
# 5. Dựng + render từ kịch bản trong manhua-series
.venv\Scripts\python ..\tools\manhua_recap\recap.py build  ..\manhua-recap\<thư mục> --script ..\manhua-series\<ten-truyen>\ep0N\script.json --name "<Tên> - Tap N"
```

Video ra ở `backend\data\library\_video_composer\job_XXX\output\<Tên>.mp4`. Lệnh `build` in ra số project.

## Setup máy mới (công ty / nhà)

1. `git pull`
2. Backend: `cd backend`, rồi `.venv\Scripts\python -m uvicorn app.main:app --port 8000`. Frontend: `cd frontend`, rồi `npm run dev`.
3. Ảnh tranh **không** được đồng bộ qua git. Ở máy mới, chạy lại bước 1 và 2 (`fetch` + `cut`) cho đúng thư mục trong `source_dir`.
   Bước cắt cho kết quả giống hệt nhau, nên tên khung (p001.jpg…) khớp với `script.json`.
   Nếu trước khi `cut` đã xóa khung rác thì phải xóa lại đúng những khung đó. Danh sách nằm trong mục "Khung đã xóa" của `SERIES.md`.
4. Database (`backend/data/library.db`) cũng **không** đồng bộ, nên số project ở hai máy sẽ khác nhau. Không sao: `build` luôn tạo project mới.

## Định dạng script.json

```json
{
  "title": "Tiêu đề video (nghịch lý + !?)",
  "chapters": "1",
  "source_dir": "manhua-recap/dqg_ep1",
  "beats": [
    {"panel": "p008.jpg", "type": "HOOK", "kind": "recap", "narration": "Câu mở nghịch lý."},
    {"panel": "p045.jpg", "type": "REACTION", "kind": "commentary", "narration": "Câu bình luận của kênh (giọng nữ)."}
  ]
}
```

Quy tắc để video đạt chuẩn:
- `panel` phải tăng dần, không dùng lại khung.
- `type`: HOOK (beat đầu), SETUP, BUILD, REVEAL, REACTION, ENDING (beat cuối).
- `kind`: `recap` (giọng nam kể) hoặc `commentary` (giọng nữ bình luận). Nên có 2–4 câu bình luận để không bị coi là "reused content".
- Độ dài: khoảng **280–310 âm tiết** là khoảng 55–60 giây (giọng đọc 5.1 âm tiết/giây).
- Beat cuối kết lửng (cliffhanger) để dẫn sang tập sau.
