# Cài đặt & chạy

## Yêu cầu
Windows 11 (đã kiểm chứng), Python 3.11, Node.js ≥ 20, ffmpeg + ffprobe trong PATH (cần có filter `sidechaincompress`), ~2 GB trống
(Chromium của Remotion tải lần render đầu; model Whisper `small` ~480 MB nếu dùng).

## Các bước
```
# 1. Backend (venv của repo)
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000        # DB + migration tự chạy khi khởi động

# 2. Remotion (package Node riêng, phiên bản ghim chính xác)
cd remotion && npm install

# 3. Frontend
cd frontend && npm install && npm run dev                            # mở /documentary
```

## Cấu hình (`backend/.env`, tiền tố `APP_`)
| Biến | Ý nghĩa | Mặc định |
|---|---|---|
| `APP_LIBRARY_DIR` | nơi lưu ảnh/audio/render (`_documentary/project_<id>/…`) | `./data/library` (tương đối so với thư mục chạy backend) |
| `APP_DATABASE_URL` | SQLite | `sqlite:///./data/library.db` |
| `APP_ELEVENLABS_API_KEY`, `_VOICE_ID`, `_MODEL_ID`, `_STABILITY`… | giọng ElevenLabs (trả phí) | chưa đặt — dùng tab "Cài đặt giọng" |
| `APP_ELEVENLABS_USD_PER_1K_CHARS` | giá gói của bạn; chưa đặt ⇒ chi phí hiển thị "chưa biết" | không có |
| `APP_DOCUMENTARY_WHISPER_MODEL` | `tiny/base/small/medium/large-v3` | `small` |
| `APP_ANTHROPIC_API_KEY` / `APP_OPENAI_API_KEY` / `APP_AI_PROVIDER` | chỉ cho provider kịch bản `llm` (tốn token) | không bắt buộc |

Khóa API chỉ ở server, không bao giờ trả về qua API/giao diện.

## Kiểm thử
```
cd backend && python -m pytest tests/modules/documentary tests/api/test_produced_videos.py -q   # ≈ 3 phút
cd remotion && npx tsc --noEmit
cd frontend && npx tsc -b --noEmit && npm run build        # dùng "-b": tsc trần không kiểm tra gì ở dự án này
```
Test render Remotion thật tự bỏ qua nếu thiếu node/ffmpeg/`remotion/node_modules`. Test không gọi API trả phí hay mạng ngoài.

## Chạy thử/e2e an toàn
`PUT /settings/*` ghi `backend/.env` **theo thư mục chạy**. Khi thử nghiệm, khởi động backend từ thư mục tạm:
```
cd <scratch> && APP_DATABASE_URL=sqlite:///<scratch>/t.db APP_LIBRARY_DIR=<scratch>/lib \
  <repo>/backend/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir <repo>/backend --port 8765
```
