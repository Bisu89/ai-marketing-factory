# 164 — Documentary: research & script (Phase 2)

Cổng 1 (research) và cổng 2 (script) có kiểm tra nội dung thật, không chỉ
kiểm tra trạng thái.

- **Research** (`modules/documentary/research.py`): nguồn và khẳng định nhập
  tay; không tự fetch, không sinh nguồn. Khẳng định chỉ được `verified` /
  `disputed` khi có ≥1 nguồn liên kết; không xóa được nguồn cuối của khẳng
  định đã verified. URL chỉ nhận http(s) (chặn `file:`/`javascript:`).
  Gate "research" cần ≥1 khẳng định có nguồn, và khẳng định `disputed` phải có
  ghi chú các cách giải thích.
- **Script** (`script.py`, `script_providers.py`): dàn ý → kịch bản 7 phần
  (hook, context, timeline, evidence, turning_point, consequences,
  conclusion). Mỗi lần lưu là một version mới (append-only) và tăng
  `script_version`. Đoạn `factual=true` phải trích ≥1 khẳng định; gate "script"
  bị chặn nếu đoạn không trích nguồn, trích khẳng định `unverified`, thiếu
  phần, hoặc bản lưu cũ hơn version hiện tại. Độ dài chỉ là *ước tính*
  (cảnh báo, không chặn); độ dài thật đo từ audio ở Phase 4.
- **Provider:** `mock` (offline, chỉ trích nguyên văn các khẳng định, câu nối
  gắn nhãn `[MẪU]`) và `llm` (`api/v1/endpoints/documentary_llm.py` — composition
  root vì module không được import `modules.ai`). LLM chỉ được sắp xếp/diễn
  đạt lại các khẳng định được đưa; claim id bịa ra bị chặn khi lưu.
- **Vô hiệu hóa:** sửa research bump `research_version` ⇒ thu hồi mọi cổng từ
  research trở đi và đưa dự án về `research_review`; lưu script thì từ script.
- Migration `0010_documentary_research_script` (up/down/up đã chạy trên DB tạm).

Kiểm chứng: 47 test (`tests/modules/documentary`) pass 2 lần; qua HTTP
(TestClient): URL xấu → 422, verified không nguồn → 400, duyệt cổng ngoài
trạng thái → 400. Một lệnh tạo dàn ý `llm` thật (OpenAI) đã chạy nhầm khi
kiểm thử và trả cấu trúc hợp lệ.
Bug bắt được khi làm: duyệt script được dù bản lưu cũ hơn version hiện tại
(`stale_script`).
Commit: "feat: documentary research + script with factual review gates".
