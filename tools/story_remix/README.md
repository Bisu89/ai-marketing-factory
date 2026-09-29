# Story Remix — video kể chuyện đang hot → 1 chương truyện xuyên không/hệ thống MỚI

Tool này tải 1-3 video kể chuyện (xuyên không/hệ thống) đang hot trên YouTube, tách
giọng đọc ra text, rồi để AI **viết lại thành một câu chuyện mới** (đổi tên nhân vật,
đổi bối cảnh, đổi kết thúc) trước khi dựng video bằng template `isekai_system_vi`.
Cần backend đang chạy và cần API key OpenAI (bước tách giọng) + AI provider bất kỳ
(bước viết lại) đã cấu hình trong Settings.

```
cd backend
.venv\Scripts\python ..\tools\story_remix\remix.py fetch  tap1 https://youtube.com/watch?v=... [url2] [url3]
.venv\Scripts\python ..\tools\story_remix\remix.py script tap1 --lang vi --notes "nhấn mạnh yếu tố tu tiên"
.venv\Scripts\python ..\tools\story_remix\remix.py build  tap1
```

1. **fetch**: tải từng video nguồn qua Download Engine có sẵn, tách giọng đọc ra text
   (OpenAI). Kết quả ghi vào `story-remix/tap1/_remix/sources.json`.
2. **script**: AI đọc transcript(s), viết lại thành MỘT chương mới -- đổi tên nhân vật,
   bối cảnh, kết thúc; nếu đưa 2-3 nguồn thì trộn chúng lại thành một câu chuyện, không
   kể lại nguyên một nguồn. Có một cổng kiểm tra tự động (`_check_transformation` +
   `_check_same_language_overlap` trong `story_remix.py`) từ chối bản nháp chưa biến
   đổi đủ mạnh và bắt AI viết lại. Kết quả ghi vào `_remix/script.json` -- **xem lại
   tay** phần `transformation` + tên/bối cảnh/kết thúc trước khi build.
3. **build**: tạo project (ảnh AI sinh mới hoàn toàn, không dùng lại gì từ video
   nguồn), PUT beat-plan, bắt đầu render. Thêm `--no-render` nếu chỉ muốn tạo project.

Lưu ý: chỉ phần TEXT cốt truyện của video nguồn đi vào bước viết lại -- hình ảnh/âm
thanh gốc không bao giờ vào bản render cuối. Xem `docs/features/155-story-remix-pipeline.md`
để biết đầy đủ lý do thiết kế và checklist YPP.
