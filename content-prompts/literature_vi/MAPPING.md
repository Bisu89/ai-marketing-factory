# MAPPING — trường kế hoạch cảnh ↔ nơi đã có trong máy dựng

Không tạo schema JSON thứ hai. Một tập = một `spec.json` theo định dạng của `content-prompts/vox_documentary_template/` (xem `templates/spec_template.json`
và ví dụ `biblical-figures-prompts/vox/ep6.spec.json`), đưa vào app bằng `tools/episode_builder.py`. Thời gian thật nằm ở timeline sinh từ audio.

## Bảng ánh xạ
| Trường mong muốn | Nơi lưu trong hệ thống | Ghi chú |
|---|---|---|
| episode_id / project | dự án documentary (`POST /projects`, id do app gán) | `builder` ghi id vào `<spec>.state.json` |
| work_title, episode_title | `title`, `topic` của spec | |
| language | `language` (spec) → dự án | `vi` mặc định (giọng `edge`); `en` dùng `edge_en` |
| target_duration | không có | độ dài thật đo từ audio; chỉ ước lượng khi lập kịch bản |
| visual_style_id | theme lúc render: `collage` (mặc định, duy nhất hiện trong tab Render) | chọn ở tab Render |
| beat_id, sequence | `scene_key` S001… + `order_index` | công cụ tự gán, ổn định, không tái dùng |
| narrative_function | `section_kind` (hook/context/timeline/evidence/turning_point/consequences/conclusion) | 7 loại cố định |
| narration_text | `narration_text` của cảnh (cắt theo câu từ kịch bản) | |
| narration_mode | **không có trường riêng** → quy ước: NGƯỜI KỂ = `factual:true`; GÓC NHÌN/BÌNH LUẬN = `factual:false` + ghi chú ở `script.md` | đề xuất: thêm trường `mode` nếu cần lọc/xuất; chưa làm |
| source_notes | `sources[]` (trích đoạn nguyên văn) + `claims[]` gắn nguồn; xuất ra `sources.json` | `fetch`: `bible`, `wikisource`, `wikipedia` (cần thêm `lang` cho `wikisource` tiếng Việt) |
| interpretation_notes | claim `status: disputed` + `note`; hoặc đoạn `factual:false` có ghi chú | |
| verification_status | `claims[].status` (`verified`/`disputed`/`unverified`) | `verified`/`disputed` bắt buộc có nguồn |
| character_ids | **không có** → ghi trong `visual_objective` và `characters.md` của tác phẩm | |
| visual_prompt | `scene_overrides[Sxxx].objective` (→ `visual_objective`) và dòng CSV prompt | CSV xuất ở tab Ảnh |
| visual_asset_ids | `images[]` (kind `file`/`commons`, `origin: ai_manual`/`archival`/`imported`) + `use` hoặc `paragraphs` | ảnh gán theo mã cảnh; tối đa 3 cảnh/ảnh |
| composition, camera_motion | `visual_preset` (9 preset) + theme; `motion_notes` | chuyển động do theme quyết định |
| on_screen_text | `scene_overrides[].texts = [[text, role]]`, role: headline/label/date/number/caption | chữ do code vẽ |
| sound_design | `sfx_cues` (ghi chú; chưa phát) + nhạc nền tùy chọn ở tab Render | SFX chưa có tính năng |
| transition | cố định (cảnh sau fade đè lên cảnh trước) | không chỉnh theo cảnh |
| estimated_duration | `expected_duration` (ước lượng) | |
| actual timing | `scene_timing` / timeline / `subtitles` (từ audio, có cờ nếu ước lượng) | tách bạch với ước lượng |

## Quy ước thêm cho kênh văn học (không cần sửa backend)
- Mỗi đoạn trong `script[]` ghi chế độ lời đọc bằng **tiền tố trong `heading` của phần** hoặc trong `script.md` (ví dụ phần "Bình luận của chủ kênh").
- Trích dẫn tác phẩm luôn là **nguồn** (excerpt nguyên văn), và khẳng định là cách diễn đạt lại ("Trong truyện, X làm Y") — không đưa câu trích vào lời đọc trừ khi nguồn chứa đúng câu đó.
- Nhân vật: bảng cast trong `characters.md`, dán dòng cast vào prompt ảnh.
- **5 nhóm biên tập (`SCRIPT_TEMPLATE.md` mục 1) không phải trường trong spec.** Chúng chỉ là tiêu đề các mục trong
  `script.md`/`heading` của từng phần; khi một nhóm biên tập trải qua nhiều `kind` kỹ thuật (ví dụ một nhóm vừa có
  `timeline` vừa có `evidence`), tạo hai phần `script[]` riêng (hai `kind` khác nhau), đặt `heading` theo kiểu
  "Phần 3 (I) — …" / "Phần 3 (II) — …" như `episodes/chi-pheo-ep01/script.md` đã làm, không gộp cứng vào một `kind`.
- `cards_by_phrase` (khớp theo cụm chữ sau khi có storyboard) được chính `episode_builder.py storyboard` xử lý —
  xem hàm `cmd_storyboard` trong file đó. Không có script `resolve_cards.py` riêng; nếu `_notes` của một spec cũ nói
  vậy thì đó là ghi chú lỗi thời, sửa lại khi chạm vào spec đó. `scene_overrides` theo khóa cảnh cố định (`S0xx`) chỉ
  dùng được sau khi đã chạy `storyboard` với đúng bản kịch bản đó; nếu kịch bản bị viết lại/đổi số đoạn, xóa
  `scene_overrides` cũ (sẽ bị công cụ báo "không còn tồn tại" và bỏ qua) và ưu tiên `cards_by_phrase` vì khớp theo
  nội dung, không theo số thứ tự.

## Đã xác nhận khi chạy tập đầu tiên (2026-10-12)
1. `episode_builder.py`: `fetch` kiểu `wikisource` đã nhận `lang` (`vi.wikisource.org`) và `page` — **đã hoạt động**,
   không còn là đề xuất (xem `fetch_source()` trong `episode_builder.py`); đã dùng thật để lấy và xác minh toàn bộ
   trích dẫn của `episodes/chi-pheo-ep01/spec.json`.
2. Theme `collage`: **chưa kiểm thử thật** dấu tiếng Việt của dải chữ cắt dán/tiêu đề trong app (cần làm trước khi
   duyệt cổng 3 của tập đầu); đổi font nếu thiếu glyph.
3. (Tùy chọn, vẫn chưa làm) trường `mode` cho đoạn kịch bản nếu muốn lưu chế độ lời đọc trong DB thay vì chỉ ghi
   trong `heading`/`script.md`.
4. Preset đặc thù văn học (thẻ trích dẫn có nguồn) — hiện dùng `EvidenceBoard`, vẫn chưa có preset riêng.

## Đã xác nhận khi chạy tập thứ hai — Lão Hạc (2026-10-13)
5. **Bẫy của hàm `excerpt()`:** chỉ kiểm `needle in text` (chuỗi con thô) là **chưa đủ** để đảm bảo trích đoạn sạch.
   Hàm chia câu bằng `para.split(". ")` (chấm + dấu cách, kể cả chấm cuối của "..."), rồi tìm đoạn chứa
   `core = needle.rstrip(".!?")`. Nếu một needle tự gộp **hai câu** (có dấu `". "` nằm giữa chính needle đó), hàm
   không tìm được mảnh nào chứa trọn needle và **rơi về nguyên cả đoạn văn dài** (biến `para` gốc) — gây trích đoạn
   bị lặp/lẫn khi nhiều needle cùng rơi vào một đoạn. Quy tắc: mỗi needle chỉ nên là **một câu** (không chứa dấu
   `". "` ở giữa); nếu cần nhiều câu liên tiếp, tách thành nhiều needle riêng. Trước khi ghi needle vào spec, chạy
   thật `eb.excerpt(text, needles)` (không chỉ `in` thô) và đọc lại kết quả để phát hiện lặp.
6. Tốc độ đọc đo được bằng `edge-tts`/`vi-VN-NamMinhNeural` cho giọng nam: **≈ 221,6 từ/phút** ở tập Lão Hạc (tập Chí
   Phèo đo được ≈ 205,7 từ/phút) — tốc độ thật dao động theo nội dung câu, không dùng một hằng số cố định để ước
   lượng thời lượng; luôn đo lại bằng audio thật trước khi chốt kịch bản đạt chuẩn 14–16 phút.
7. Truyện ngắn hơn (ít nhân vật/mốc thời gian hơn Chí Phèo) dễ ra bản kịch bản đầu tiên **ngắn hơn chuẩn 14–16
   phút** dù đã dùng hết các đoạn nổi bật nhất; cách bù hợp lệ là khai thác thêm các đoạn **ít được trích** của
   chính văn bản (chi tiết phụ, miêu tả ngắn) và mở rộng lớp BÌNH LUẬN bằng phân tích thật (số liệu, kỹ thuật tự
   sự, so sánh có căn cứ) — không lặp ý, không thêm triết lý sáo rỗng, không kéo dài bằng đọc chậm.
