# 175 — Documentary: tiếng Anh + Biblical Figures tập 6 theo phong cách Vox

Series Biblical Figures (tiếng Anh) chuyển sang quy trình Vox, bắt đầu từ tập 6 (John the Baptist). Dự án #2 trong app, tạo bằng `episode_builder.py`; **chưa duyệt cổng nào** (việc của người dùng).

- **Giọng tiếng Anh**: backend TTS mới `edge_en` (edge-tts `en-US-GuyNeural`, miễn phí, có timestamp từng từ). Tách backend riêng nên dự án tiếng Việt giữ nguyên cache audio. Nhãn trên hình theo `project.language`: "AI illustration" / "Image: …" cho tiếng Anh.
- **Nguồn gốc thật**: `episode_builder.py` thêm `fetch` cho nguồn — `bible` (World English Bible, public domain, bible-api.com), `wikisource` (Josephus bản Whiston), `wikipedia` — trích nguyên văn, không gõ lại; tạo dự án truyền `language`; ảnh gán theo `paragraphs` (cảnh cắt từ đoạn kịch bản, tối đa 3 cảnh/ảnh).
- **Spec**: `biblical-figures-prompts/vox/ep6.spec.json` (19 nguồn, 27 khẳng định, 39 đoạn, 1.198 từ, 37 ảnh Baroque sẵn có: 34 của tập 6 + 3 từ kho). Kịch bản sửa so với bản cũ cho khớp nguồn: bỏ "months later" (nguồn không nói), bỏ chi tiết pháo đài Machaerus không có nguồn, thuyết Essene ghi rõ là giả thuyết (`disputed`), thêm câu outro cố định của series.
- Giới hạn: Whisper vẫn mặc định `vi` (dùng `method="tts"` cho tiếng Anh); luật số lớn/năm của storyboard là tiếng Việt, cảnh tiếng Anh chủ yếu ra `PhotoKenBurns`.
Commit: "feat: documentary English voice backend + Biblical Figures ep6 Vox spec".
- Nút **Duyệt tất cả ảnh đang chờ** ở tab Ảnh (có hộp xác nhận): chỉ gồm ảnh AI/tự nhập; ảnh tư liệu vẫn phải đọc giấy phép và duyệt riêng. Endpoint nhập ảnh nhận thêm `origin=ai_manual`.
- Theme **poster** (kiểu vox-director): ảnh poster collage tràn khung (do bạn tạo từ CSV), confetti giấy bay, chuyển động đẩy nhẹ, chữ tiêu đề cắt dán, phụ đề viền đen. Thử 6 cảnh tập 6: `biblical-figures-prompts/vox/poster_test/`.
