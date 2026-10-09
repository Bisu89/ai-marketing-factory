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
| visual_style_id | theme lúc render: `poster` / `cinematic` / `collage` | chọn ở tab Render |
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

## Việc cần sửa nhỏ khi bắt đầu tập đầu tiên (đề xuất, chưa làm)
1. `episode_builder.py`: cho `fetch` kiểu `wikisource` nhận `lang` (`vi.wikisource.org`) và `page`.
2. Theme `poster`: kiểm thử dấu tiếng Việt của tiêu đề; đổi font nếu thiếu glyph.
3. (Tùy chọn) trường `mode` cho đoạn kịch bản nếu muốn lưu chế độ lời đọc trong DB.
4. Preset đặc thù văn học (thẻ trích dẫn có nguồn) — hiện dùng `EvidenceBoard`.
