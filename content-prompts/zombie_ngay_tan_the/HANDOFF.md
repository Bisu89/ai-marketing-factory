# NGÀY TÀN — HANDOFF (đọc file này đầu tiên khi mở session mới)

Series zombie sinh tồn gốc, **ưu tiên bản tiếng Hàn (KO)**, bản Việt (VI) làm sau. Không có "Hệ Thống". Toàn bộ nhân vật chính là người trưởng thành.

## Trạng thái hiện tại
| Hạng mục | Tập 1 | Tập 2 |
|---|---|---|
| Cốt truyện (SERIES.md §6) | xong | xong (bản của chủ series, chỉ vá logic nhỏ) |
| Lời đọc VI | `scripts/ep1_audiobook_v3.txt` (đã có `## GIỚI THIỆU/TRUYỆN/KẾT`) | `scripts/ep2_audiobook_v1.txt` (nháp, chờ duyệt) |
| Lời đọc KO | `scripts/ep1_ko.md` (dịch từ v3, chờ người đọc Hàn soát) | **chưa dịch** |
| Giới thiệu/kết KO | trong `scripts/ko_bookends_check.txt` (E1_*) | trong cùng file (E2_*) |
| CSV ảnh | `ngay_tan_ep1_scenes_v3.csv` (100 ảnh) + `ngay_tan_ep1_shotlist.md`; **short**: 14 ảnh dọc (xem mục Video SHORT) | **chưa làm** (long + short) |
| Ảnh đã tạo | bảng nhân vật tổng hợp (7 người) của chủ series; bảng zombie | — |

Chủ series chưa báo kết quả tạo thử ảnh (đặc biệt chữ hiệu ứng Hangul và ảnh nhiều nhân vật).

## Đọc theo thứ tự để làm Tập 2
1. `HANDOFF.md` (file này).
2. `SERIES.md` — §1 quy tắc nội dung, §3 nhân vật, §4 bestiary, §5 logic sinh tồn (sổ tài nguyên 5.9), §6.0 cách nhóm hình thành, **§6 Tập 2** (và Tập 3 để biết cliffhanger). Đầu file có quy tắc giọng đọc.
3. `scripts/ep2_audiobook_v1.txt` — lời đọc VI Tập 2 (ngôi "tôi" Taeho; cảnh Jiwoo/Yerin kể lại).
4. `scripts/ko_ep1_check.txt` + `scripts/ep1_ko.md` + `scripts/ko_bookends_check.txt` — mẫu phương pháp dịch Hàn và định dạng.
5. `IMAGE_SYSTEM.md` (khối prompt, mục C2 quái vật, mục I khung bảng chuẩn) và `ngay_tan_series_library.csv` (bảng quái vật đã có prompt).
6. `ngay_tan_ep1_shotlist.md` + `_tools/build_ep1_csv.py` — mẫu cách chia ảnh theo đoạn.
7. Memory: `project_ngay_tan_series.md`.

## Quy trình cho một tập mới (đã dùng ở Tập 1)
1. **Lời đọc VI** (ngôi "tôi", câu ngắn, không khẩu hiệu dạy đời) → thêm `## GIỚI THIỆU` / `## TRUYỆN` / `## KẾT`.
2. **Dịch KO** bằng *phương pháp file kiểm tra đánh số*: viết câu Hàn **ngắn** vào `scripts/ko_epN_check.txt` dạng `PNN-S|câu` → đọc lại bằng Read để soát ký tự lạ → ghép bằng `_tools/build_ko_md.py` ra `scripts/epN_ko.md`. Không bao giờ gõ thẳng đoạn Hàn dài (từng làm hỏng chữ). Giọng truyện: văn tiểu thuyết ngôi thứ nhất (한다체); giới thiệu/kết: 합쇼체.
3. **Giới thiệu + kết mỗi tập**: KO = giọng chính nữ (`ko-KR-SunHiNeural`), giới thiệu/kết nam (`ko-KR-InJoonNeural`); VI = giọng chính nam (`vi-VN-NamMinhNeural` 1.10x), giới thiệu/kết nữ (`vi-VN-HoaiMyNeural`). Kết hẹn tên tập sau.
4. **Shot list ~100 ảnh/tập** (≈6 giây/ảnh), bám từng đoạn kịch bản Hàn, ưu tiên A/B/C. Copy `_tools/build_ep1_csv.py` thành `build_epN_csv.py`, thay danh sách `S(...)`. Tên file ảnh `NNN_slug.png`; tag: `ngay_tan, tapN, vi, ko, tai_su_dung|rieng_tapN, uutien_X` + từ khoá Việt + từ khoá Hàn.
5. Prompt ảnh **viết tiếng Việt**; nhân vật chỉ **gọi tên theo bảng tổng hợp** (KANG TAEHO 강태호, SEO JIWOO 서지우, HAN YERIN 한예린, SEO AREUM 서아름, LEE MINSEO 이민서, CHOI GANGSIK 최강식, BAEK DAHEE 백다희) (bảng tổng hợp đã được tạo sẵn ở đầu cuộc trò chuyện GPT của chủ series, prompt chỉ **gọi lại theo tên**, không đính kèm/up lại ảnh); chỉ mô tả khi trang phục đổi/rách/bẩn. Quái vật cũng gọi theo **tên + số** trong bảng quái vật tổng hợp (1 Kẻ Lang Thang … 10 Kẻ Nở Hoa, biến thể 11–18; danh sách đầy đủ ở cuối IMAGE_SYSTEM.md; Kẻ Săn Mồi số 1 = ô 5) — **không dùng ô 17 Học Sinh** (không vị thành niên). Cảnh hành động/tiếng động có **chữ hiệu ứng Hangul** (쾅!, 꺄악!, 삐뽀삐뽀...); cảnh đọc/thoại không chữ.
6. Thử giọng bằng menu "Thử giọng đọc" (dán file có các mục `##`), rồi mới dựng.

Tập 2 cần chú ý ảnh: Jiwoo, Yerin, Areum xuất hiện lần đầu (đã có trong bảng tổng hợp); Kẻ Lang Thang + Thể Cuồng (Runner); Areum giương cung cuối tập.

## Video SHORT (mỗi tập có 1 video short 9:16)
Tập 1 đã có: lời đọc `scripts/ep1_short_vi.txt` + `scripts/ep1_short_ko.md` (từ `scripts/ko_ep1_short_check.txt`, KO đo thật ~66s), CSV 14 ảnh dọc `ngay_tan_ep1_short_scenes.csv` (tag `short, 9x16, rieng_short_tap1`), shot list `ngay_tan_ep1_short_shotlist.md`, công cụ `_tools/build_ep1_short.py` (copy cho tập khác). Short = hook (giọng giới thiệu) + tóm các nhịp then chốt của tập (ngôi "tôi") + kết kêu gọi xem tập đầy đủ và tập sau; ảnh dọc dựng lại bố cục (chừa chỗ phụ đề). Tập 2 cũng cần 1 short.

## Dựng thử trong app (đã chạy cho Tập 1)
`_tools/render_episode.py N` (backend phải đang chạy): đăng ký ảnh trong `ngay_tan_epN_images/` (tag từ CSV) → tạo project template `ngay_tan_ko` → beat plan (mỗi shot = 1 beat, đã gán ảnh; lời đọc rải theo shot; giới thiệu/kết beat riêng giọng InJoon) → Factory run. Cần `ngay_tan_epN_shotlist.md`, `ngay_tan_epN_scenes_v3.csv`, `scripts/ko_epN_check.txt`, E{N}_ trong `ko_bookends_check.txt`. Tên file ảnh phải đúng CSV (lần đầu có 2 file gõ sai tên, đã đổi lại).
Kết quả Tập 1 (long, KO): project 163, render job 222, 11:47, 1080p, QA PASS 100; thời gian ~20 phút (voice ~1', motion ~10', render ~9'). Quality Gate cho NEEDS_REVIEW 82 (chỉ cảnh báo: pacing, 100 beat cùng loại BODY, ảnh bị coi "độ phân giải thấp" vì ảnh ChatGPT nhỏ hơn 1920x1080) → dùng `POST /factory-runs/{id}/continue?force=true` để chấp nhận cảnh báo và render. Mô tả/hashtag tự sinh bằng tiếng Anh (cần sửa tay).

## Quy tắc chủ series đã nhắc (đừng vi phạm)
- Beat do chủ series viết (Tập 1, Tập 2): chỉ làm mượt câu chữ; ý mới đưa vào mục "đề xuất" riêng, không tự nhét vào cốt truyện.
- Không khẩu hiệu/"bài học sinh tồn". Sinh tồn qua hạn chế thật + hậu quả (SERIES §5).
- Nhóm không thành đội ngay: mỗi người nhập có điều kiện, ma sát (SERIES §6.0). Đội thật từ Tập 5.
- Máu = chất lỏng đen sẫm; không nội tạng; nữ chiến binh không bị cắn trên màn hình; không nhân vật vị thành niên; trang phục "ít vải" chỉ ở mức tinh tế, không khoả thân.
- Không đặt tên vũ khí thật trong prompt ảnh.
- Prompt ảnh chỉ dùng **từ có trong bảng nhân vật/quái vật** (tên + số). GPT không hiểu từ nội bộ như "Subject-03" hay "Kẻ Săn Mồi số 1": gọi là "KẺ SĂN MỒI (số 5 trong bảng)".
- Muốn **nhiều ảnh** (đầu tư giữ chân người xem), không rút gọn xuống 20 ảnh/tập.

## Việc còn mở
- Chủ series duyệt Ep1 v3 (VI) và `ep1_ko.md`; thử tạo ảnh nhóm A (ví dụ ảnh 6, 99, 100 và cảnh có hai nhân vật).
- Tập 2: dịch KO + shot list + (có thể) 2 câu thoại đề xuất cho Taeho–Jiwoo (Jiwoo: "đưa tôi tới chỗ em gái, tôi dẫn anh đi đường tắt"; Taeho: "tôi không hứa gì ngoài chuyện đó") — **chưa áp dụng vào bản của chủ series**.
- SERIES §5.8 (sai lầm Taeho Tập 3–4) chưa chỉnh khớp Tập 3–4 mới; §8 có các câu hỏi chờ quyết (Dahee có chuộc lỗi không, thêm nam phụ T5, mức trang phục, tên series).
- Tên series bản Hàn tạm: 종말의 날.
- Giữ Tập 3–4 theo SERIES §6 (đã vá logic: hầm sơ tán nối Cheonma–ga Euljiro, Thể Giáp bị kiểm soát bằng liều ức chế, Subject-03 = Kẻ Săn Mồi số 1).

## Công cụ & cạm bẫy kỹ thuật
- Template trong app: `ngay_tan_ko` (KO, SunHi 1.0), `ngay_tan` (VI, NamMinh 1.10) — `backend/app/modules/beat/schemas.py`. Menu "Thử giọng đọc": `frontend/src/pages/VoiceTestPage.tsx`, `backend/app/api/v1/endpoints/voice_test.py` (docs/features/160, 162).
- `_tools/`: `ngay_tan_blocks.py` (khối prompt), `build_ep1_csv.py` (CSV + shot list), `build_ko_md.py` (ghép md Hàn). Chạy từ thư mục `_tools/`.
- **CSV đang mở bằng Excel sẽ bị khoá** (PermissionError khi ghi) — nhờ chủ series đóng file hoặc xuất ra tên mới.
- Trên máy này, lệnh `python - <<'PY' ... PY` dài/nhiều dấu nháy trong Bash hay lỗi; hãy ghi script ra file rồi chạy. Không dùng đường dẫn `/tmp` cho Python (Windows).
- Đừng cắt/ghép SERIES.md bằng `str.index('---')` (từng xoá nhầm nửa file); dùng Edit hoặc neo chuỗi dài, duy nhất.
- `git fetch` trước khi giả định local mới nhất (có session khác). Không đụng các file untracked của session khác (`manhua-series/…`, `biblical-figures-prompts/…`).
- Commit kèm dòng `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; chủ series đã cho phép tự commit/push.
