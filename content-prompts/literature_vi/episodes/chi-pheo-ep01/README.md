# Chí Phèo — tập 1 (ví dụ minh họa template kênh văn học)

Đây là **một ví dụ** để kiểm chứng template (`../../CHANNEL.md`, `VISUAL.md`, `SCRIPT_TEMPLATE.md`, `MAPPING.md`); tác phẩm khác copy `../_TEMPLATE/`.

- **Mục tiêu tập:** giúp người chưa đọc Chí Phèo hiểu vì sao điều nhỏ nhất hắn xin (được lương thiện) lại không thể có.
- **Câu hỏi trung tâm (giả thuyết):** vì sao mong muốn trở lại cuộc sống bình thường, tử tế của Chí Phèo trở thành bi kịch?
- **Góc nhìn đề xuất (chờ chủ kênh chốt):** "lương thiện" cần được người khác công nhận; cả Bá Kiến, bà cô lẫn vết sẹo đều chặn điều đó. Có cách đọc khác (trách nhiệm cá nhân) và kịch bản nêu cả hai.
- **Khán giả:** người chưa đọc truyện, học sinh, người lớn quan tâm tâm lý xã hội.
- **Thumbnail:** nền màu phẳng đỏ gạch, [Chi Pheo CAST] mặt lớn bên phải nhìn thẳng, 1/3 trái tối chừa chỗ chữ ≤ 4 từ ("AI CHO TAO LƯƠNG THIỆN?"); chữ do người làm đặt.
- **Shorts gợi ý (25–30 giây):** (1) bát cháo hành: "người ta hay hối hận khi không đủ sức mà ác nữa"; (2) câu hỏi "Ai cho tao lương thiện?"; (3) vì sao lò gạch ở đầu và cuối truyện.
- **Âm thanh gợi ý:** tiếng chai vỡ, gió ruộng, bát sứ chạm bàn, một nhịp lặng trước câu "Ai cho tao lương thiện"; không nhạc nền (hoặc rất nhỏ).
- **Câu hỏi cuối cho khán giả:** có sẵn ở đoạn cuối của kịch bản.

## Kiểm chứng đã làm / còn lại
- Văn bản truyện lấy từ Wikisource tiếng Việt; **mọi trích đoạn nguồn** trong `spec.json` được công cụ cắt nguyên văn (0 lỗi khi chạy).
- **Đã chạy thật** `episode_builder.py create` trên backend tạm (DB riêng): 8 nguồn, 15 khẳng định, kịch bản qua kiểm tra nguồn (`script review: OK`). Phát hiện: máy dựng bắt buộc đủ 7 phần (có `timeline`) nên template đã sửa.
- **Chưa** tạo dự án trong DB thật, chưa chạy cổng duyệt, chưa tạo ảnh/giọng/render.
- Kịch bản ~782 từ ≈ 5–6 phút: ngắn hơn khung 6–9 phút; chủ kênh bổ sung phần bình luận và đo lại bằng audio thật.
- Đoạn BÌNH LUẬN là **bản nháp** do AI viết; chủ kênh viết lại bằng giọng của mình trước cổng 2.
- Cần đối chiếu một bản in (chính tả cũ/hiện đại, văn bản Wikisource có thể khác bản nhà xuất bản).
- Việc nhỏ cần làm khi chạy lần đầu: kiểm thử dấu tiếng Việt của chữ cắt dán trong theme collage.

## Chạy
`python content-prompts/vox_documentary_template/tools/episode_builder.py create content-prompts/literature_vi/episodes/chi-pheo-ep01/spec.json`
(backend chạy từ thư mục tạm; không bật `.env` thật). Sau đó duyệt cổng 1–2 trong app, `storyboard`, thêm `scene_overrides`/`images`, giọng `edge` tiếng Việt, render **collage** (tắt ảnh đen trắng).
