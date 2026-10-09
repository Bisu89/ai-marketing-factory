# 176 — Template kênh văn học (collage) + ví dụ Chí Phèo

Bộ template cho nhiều tác phẩm trong `content-prompts/literature_vi/`: `CHANNEL.md`, `VISUAL.md` (collage, ảnh kiểu poster trong khung giấy), `SCRIPT_TEMPLATE.md` (3 chế độ lời đọc), `MAPPING.md` (trường kế hoạch cảnh ↔ máy dựng, không tạo schema thứ hai), `PROMPT.md` (prompt khởi tạo đã sửa).
`episodes/_TEMPLATE/` là khung chép cho tác phẩm mới; `episodes/chi-pheo-ep01/` là ví dụ (spec 8 nguồn nguyên văn từ Wikisource tiếng Việt, 15 khẳng định, 27 đoạn ≈ 782 từ, characters, image_prompts).
Công cụ: `episode_builder.py` lấy nguồn `wikisource` có `lang`; **sửa lỗi** hàm cắt trích đoạn trả cả đoạn dài khi cụm cần cắt kết thúc bằng dấu chấm (vượt 5000 ký tự).
Kiểm chứng: mọi trích đoạn khớp nguyên văn; `create` chạy thật trên backend tạm → kịch bản qua kiểm tra; lỗi bắt được: máy dựng đòi đủ 7 phần (thiếu `timeline`).
Giới hạn: chưa tạo dự án trong DB thật, chưa ảnh/giọng/render; bình luận là bản nháp của AI; kịch bản 5–6 phút ngắn hơn khung 6–9; dấu tiếng Việt của chữ cắt dán chưa kiểm thử.
Commit: "feat: literature channel episodes (template + Chi Pheo example), builder wikisource lang + excerpt fix".
