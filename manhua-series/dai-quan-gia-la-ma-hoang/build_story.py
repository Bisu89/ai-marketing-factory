"""Regenerate STORY.md (story-so-far reference for writing) from the Long scripts.

Run after finishing each new Long: add its folder name to LONGS, then
    python manhua-series/dai-quan-gia-la-ma-hoang/build_story.py
Each section of a Long becomes one chapter entry: the recap narration in order
(commentary beats are channel opinion, not plot, so they are left out).
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
LONGS = ["long_1_10", "long02", "long03", "long_21_30", "long_31_40", "long_41_50", "long_51_55", "long_56_60", "long_61_65", "long_66_70", "long_71_75", "long_76_80"]

out = ["# Đại Quản Gia Là Ma Hoàng — cốt truyện đã làm video",
       "",
       "Tài liệu tham chiếu để viết truyện/kịch bản. Tự sinh bởi `build_story.py` từ lời kể trong các `long_*/script.json` "
       "(chỉ phần kể, bỏ bình luận kênh). Nhân vật và bối cảnh gốc xem `GPT_SCRIPT_PROMPT.md` và `SERIES.md`.",
       "",
       "**Quy ước:** mỗi khi xong một video Long mới, thêm tên thư mục vào `LONGS` trong `build_story.py` rồi chạy lại file này.",
       ""]
for name in LONGS:
    s = json.loads((HERE / name / "script.json").read_text(encoding="utf-8-sig"))
    out += [f"## Chương {s['chapters']}", ""]
    sec, buf = None, []
    def flush():
        if sec is not None:
            out.extend([f"### {sec}", "", " ".join(buf), ""])
    for b in s["beats"]:
        if "section" in b:
            flush(); sec, buf = b["section"], []
        if b.get("kind") != "commentary":
            buf.append(b["narration"].strip())
    flush()
(HERE / "STORY.md").write_text("\n".join(out), encoding="utf-8")
print("STORY.md", len(out), "lines")
