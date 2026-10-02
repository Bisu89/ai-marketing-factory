# Biblical Figures — hồ sơ series

Phim tài liệu tiểu sử tiếng Anh, dài 10-15 phút (16:9) + Short tóm tắt (9:16), mỗi tập kể về MỘT
nhân vật trong Phúc Âm hoặc buổi đầu Cơ Đốc giáo. Xử lý như lịch sử/văn hóa, không phải thần học:
tách rõ điều đã ghi chép (Kinh Thánh + sử gia ngoài đạo như Josephus, Tacitus, Philo) khỏi truyền
thống và truyền thuyết hậu thế, trung lập giáo phái.

Quy tắc kỹ thuật đầy đủ (style ảnh, giới hạn reuse, thông số render) nằm ở [RULES.md](RULES.md).
Ghi chú nội dung từng tập nằm ở [EPISODES.md](EPISODES.md). File này là bức tranh tổng quan +
trạng thái sản xuất.

## Vì sao làm series này

Kênh thực tế đã cho dữ liệu: video dùng ảnh kiểu **tranh sơn dầu cổ** có view thật (một video non-
series ban đầu ~70 view), còn video dùng ảnh kiểu "điện ảnh AI" bóng bẩy thì 0 view sau 2 ngày. Từ
tập 2, series chuyển hẳn sang phong cách tranh cổ và không quay lại kiểu cũ.

## Công thức kênh

- Mở đầu bằng một bí ẩn hoặc hiểu lầm phổ biến về nhân vật ("Ai cũng nghĩ X, nhưng...").
- Thân bài: thế giới La Mã/Do Thái thế kỷ 1 → nhân vật là ai → bước ngoặt/sự kiện → số phận → ảnh
  hưởng để lại — luôn phân biệt rõ ghi chép / truyền thống / truyền thuyết.
- Kết bằng câu hỏi mở, không chốt một đáp án duy nhất cho các điểm còn tranh cãi.
- Outro cố định (bản dài): *"If you made it this far, subscribe -- a new figure from history every
  week."*
- Không nhạc nền. Không AI metadata (tiêu đề/mô tả tự viết tay, kiểm soát chất lượng).

## Phong cách hình ảnh

**"mini_low"** (từ tập 2, xem RULES.md §0): app tự tạo bằng `gpt-image-1-mini` chất lượng `low`
(~$0.006/ảnh) — chính model/chất lượng rẻ này cho ra chất tranh bạc màu, mềm, đúng công thức của
video từng có view thật. Ảnh dùng chung được lưu vào kho (`_pool/pool.csv`), tái sử dụng giữa các
tập để giảm số ảnh phải tạo mới mỗi tập.

Ngoại lệ lịch sử: ảnh tập 1 (cả dài+short) và short tập 2 dùng style "cinematic" cũ, tạo tay qua
ChatGPT trước khi đổi hướng — vẫn giữ nguyên, không làm lại, nhưng không trộn lẫn vào kho `mini_low`.

## Dàn nhân vật cố định (`_tools/bf_style.py`)

| Khóa | Nhân vật | Xuất hiện lần đầu |
|---|---|---|
| J | Judas Iscariot | Ep1 |
| JC | Jesus of Nazareth (lộ mặt từ Ep2) | Ep1 |
| C | Caiaphas | Ep2 |
| P | Pontius Pilate | Ep2 |
| MM | Mary Magdalene | Ep3 |
| PT | Simon Peter | Ep4 |
| PL | Paul of Tarsus | Ep4 (phụ), chính ở Ep5 |
| HA | Herod Antipas | Ep2 (phụ), Ep6 (phụ), chính ở Ep8 |
| B | Barabbas | Ep2 (phụ) |
| HD | Herodias | Ep6 (phụ), nối sang kết cục ở Ep8 |
| JB | John the Baptist | Ep6 |
| AN | Annas | Ep7 |

Nhân vật mới cho mỗi tập 5-15 liệt kê trong [EPISODES.md](EPISODES.md), thêm vào `CHAR`/`CHAR_NAMES`
trong `bf_style.py` một lần duy nhất khi tập đó được viết.

## Trạng thái sản xuất

| # | Nhân vật | Project (dài/short) | Thời lượng dài | QA | Ảnh mới/lặp/kho | Trạng thái |
|---|---|---|---|---|---|---|
| 1 | Judas Iscariot | 109 / 104 | 12:47 | PASS 100 | 76 mới (tạo tay, style cinematic) | ✅ |
| 2 | Pontius Pilate | 119 / 120 | 12:40 | PASS 100 | 30 mới / 0 / 0 (short: 7 tạo tay) | ✅ |
| 3 | Mary Magdalene | 126 / 127 | 9:58 | PASS 100 | 34 mới / 7 lặp / 4 kho | ✅ |
| 4 | Simon Peter | 143 / 144 | 9:45 | PASS 100 | 34 mới / 2 lặp / 8 kho | ✅ |
| 5 | Paul of Tarsus | 146 / 145 | 9:00 | PASS 100 | 34 mới / 1 lặp / 7 kho | ✅ |
| 6 | John the Baptist | 148 / 147 | 7:38 | PASS 100 | 34 mới / 1 lặp / 3 kho | ✅ |
| 7 | Caiaphas | 159 / 160 | 10:11 | PASS 100 | 30 mới / 1 lặp / 8 kho (short: 7 mới, 33s) | ✅ |
| 8 | Herod Antipas | — | — | — | — | ⏳ |
| 9 | Thomas | — | — | — | — | ⏳ |
| 10 | James, Brother of Jesus | — | — | — | — | ⏳ |
| 11 | Barabbas | — | — | — | — | ⏳ |
| 12 | Nicodemus & Joseph of Arimathea | — | — | — | — | ⏳ |
| 13 | Mary, Mother of Jesus | — | — | — | — | ⏳ (tập nhạy cảm nhất — đọc kỹ EPISODES.md) |
| 14 | Herod the Great | — | — | — | — | ⏳ |
| 15 | Stephen, the First Martyr | — | — | — | — | ⏳ (nối mạch với Ep5 Paul) |

Kho ảnh hiện tại (`_pool/pool.csv`, 2026-10-01): **284 ảnh** — 194 `mini_low` (Ep2-6) dùng lại được,
90 `cinematic` cũ (Ep1 + short Ep2) không trộn lẫn.

## Quy trình một tập (xem chi tiết ở RULES.md)

```
cd biblical-figures-prompts
python _tools/bf.py prompts N          # viết CSV ảnh mới từ spec, kiểm tra luật reuse
python _tools/bf.py aigen N long       # app tự tạo ảnh mới qua OpenAI (gpt-image-1-mini, low)
python _tools/bf.py aigen N short
python _tools/bf.py build N long       # import ảnh, tạo project, render
python _tools/bf.py build N short
python _tools/bf.py pool               # cập nhật lại kho sau khi có ảnh mới
```
Cần `backend/.venv/Scripts/python.exe` và backend đang chạy ở cổng 8000.

## Sự cố thật đã gặp (để tránh lặp lại)

- **Một ảnh có thể bị OpenAI chặn kiểm duyệt** dù nội dung vô hại (gặp ở Ep4: cảnh chữa bệnh cho mẹ
  vợ Peter). `aigen` đã sửa để một ảnh lỗi không làm hỏng cả loạt — chạy lại lệnh `aigen` sẽ chỉ tạo
  nốt ảnh còn thiếu.
- **Model không vẽ đúng "thập giá lộn ngược"** (tử đạo Peter) — lần vẽ bình thường (sai), lần vẽ đúng
  chiều lại lơ lửng giữa trời như biểu tượng phản Cơ Đốc. Cách né: mô tả thập giá **nằm trên đất**
  đang chuẩn bị dựng, để lời kể (không phải ảnh) mang chi tiết "lộn ngược".
- **Giới hạn mô tả trong app là 500 ký tự** — mô tả YouTube đầy đủ luôn nằm trong file
  `..._title_description.txt`, bản rút gọn mới đưa vào app.
- **Nhầm thư mục ảnh dài/short** từng xảy ra ở Ep2 — luôn kiểm `ls biblical_figures_epN_*_images/`
  trước khi build.
