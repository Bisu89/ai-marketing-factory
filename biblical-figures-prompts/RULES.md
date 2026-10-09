# Biblical Figures — Rule sản xuất (từ tập 2 trở đi)

## 0. Cách tạo ảnh (từ 28/09, thay cho tạo tay bằng ChatGPT)
App tự tạo ảnh bằng API: **`gpt-image-1-mini`, chất lượng `low`** (~$0.006/ảnh) — đúng công thức của video cũ có view (project 91); chính model/chất lượng này cho ra chất tranh cổ bạc màu.
- Long: **~25–30 ảnh mới**, các beat còn lại dùng `{"repeat": "<stem>"}` (1 ảnh tối đa 3 beat, cách nhau ≥3 beat). 3 beat đầu luôn ảnh riêng.
- Lệnh: `python _tools/bf.py prompts N` → `python _tools/bf.py aigen N long` → `python _tools/bf.py build N long`.
- Mặt nhân vật không khóa chặt như ChatGPT tay — chấp nhận đổi lấy tốc độ/chi phí.

## 1. Thông số
| | Long | Short |
|---|---|---|
| Thời lượng | 10–15 phút (~1.500–2.000 từ) | ~25–30 giây (~75–90 từ) |
| Khung hình | 16:9 `SOCIAL_LANDSCAPE` | 9:16 `SOCIAL_VERTICAL` |
| Giọng | edge_tts `en-GB-RyanNeural` 0.95, ngừng 0.5s | cùng giọng, **1.1**, ngừng 0.2s |
| Ảnh | 1 ảnh / 8–12 giây (~60–76 beat) | 6–8 ảnh |
| Motion / phụ đề | `SLOW_PUSH_IN` MEDIUM + auto-rotate / `cinematic` | `SLOW_PUSH_IN` MEDIUM + auto-rotate / **`word_pop`** (mỗi lần 1 từ, có màu -- template mượn từ series manhua) |
| Nhạc nền / outro | tắt / có | tắt / không |

Tiếng Anh, không nhạc nền, ảnh tạo bằng ChatGPT Go. Nội dung: lịch sử, không thần học; tách rõ ghi chép / truyền thống / truyền thuyết; bạo lực chỉ bằng biểu tượng.

**Phong cách ảnh (từ tập 2): tranh sơn dầu cổ kiểu Baroque** (Caravaggio/Rembrandt) — nét cọ, vết nứt sơn, tông sepia/nâu, ánh nến. Lý do: kênh thực tế — video dùng ảnh kiểu tranh cổ có view, video ảnh "điện ảnh" AI bóng bẩy 0 view; chủ đề Kinh Thánh hợp tranh cổ. Chúa Giêsu **được lộ mặt** theo kiểu tranh truyền thống (khuôn mặt cố định trong `bf_style.py`), không hào quang. Ảnh tập 1 + short tập 2 là kiểu cũ "cinematic" — công cụ **không cho dùng lại** ảnh khác phong cách.

**Thumbnail:** mỗi tập Long có 1 ảnh thumbnail riêng (dòng `T` trong CSV): mặt nhân vật chính rất to bên phải, nhìn thẳng, 1/3 trái tối để chèn 2–4 chữ to. Không import vào app — upload thẳng lên YouTube.

## 2. Tái sử dụng ảnh (MỚI)
Mọi ảnh đã làm nằm trong **kho ảnh** `_pool/pool.csv` (tên file, khung, nhân vật trong ảnh, luật dùng lại, đã dùng ở tập nào).

- `reuse = any` — cảnh rộng, đồ vật, biểu tượng, Chúa Giêsu quay lưng: dùng cho **mọi tập**.
- `reuse = with:judas` (hoặc `pilate`, `caiaphas`…) — chỉ dùng khi nhân vật đó **có trong câu chuyện** của tập.
- `avoid: …` / `never as thumbnail` — ảnh có vấn đề, công cụ chặn (trừ khi ghi `"force": true`).

Luật dùng lại:
1. **Ảnh mới bắt buộc** cho: 3 beat mở đầu (hook), mọi cảnh có **nhân vật chính của tập**, sự kiện riêng của tập, và thumbnail.
2. **Dùng lại được** cho: bối cảnh (Jerusalem, Đền Thờ, đường La Mã, Galilee, đám đông, lính La Mã), đồ vật (cuộn giấy, đèn dầu, đồng xu), biểu tượng.
3. Một ảnh **chỉ xuất hiện 1 lần** trong một video. Hạn chế dùng ảnh mà tập liền trước đã dùng (công cụ cảnh báo).
4. Không lấy ảnh 16:9 cho Short hoặc ngược lại.
5. Mục tiêu mỗi tập Long: **~30–40 ảnh mới + phần còn lại dùng lại**. Short: ảnh mới là chính (chỉ 6–8 ảnh).

Kho lớn dần sau mỗi tập — càng về sau càng ít ảnh phải tạo.

## 3. Quy trình mỗi tập
1. Claude viết `biblical_figures_ep<N>_spec.json` (kịch bản + chọn ảnh dùng lại / mô tả ảnh mới).
2. `python _tools/bf.py prompts <N>` → kiểm tra luật ở mục 2 và xuất:
   - `biblical_figures_ep<N>_long_scenes.csv`, `..._short_scenes.csv` — **chỉ ảnh MỚI** (định dạng giống zombie)
   - `..._script.md` (lời đọc từng beat, ghi rõ ảnh nào dùng lại), `..._title_description.txt`
3. Bạn tạo ảnh mới bằng ChatGPT Go, đặt đúng tên file, bỏ vào `biblical_figures_ep<N>_long_images/` / `_short_images/`.
4. `python _tools/bf.py build <N> long` và `... build <N> short` → import ảnh mới, tạo project, render. Ảnh mới tự vào kho.

(Chạy bằng python của backend: `backend/.venv/Scripts/python.exe`; backend phải đang chạy ở cổng 8000.)

## 4. Định dạng spec
```json
{
  "episode": 2, "figure": "Pontius Pilate",
  "cast": ["pilate", "jesus", "caiaphas"],
  "characters": {"X": "recurring character ...: ...; keep ... identical whenever he appears"},
  "thumbnail": {"stem": "pilate_face", "scene": "Pilate's face in extreme close-up ...", "chars": ["P"]},
  "reference": {"stem": "pilate_reference", "scene": "Character reference portrait of Pilate ...", "chars": ["P"]},
  "long": [
    {"narration": "...", "new": {"stem": "pilate_judgement_seat", "tags": "pilate, trial", "scene": "...", "chars": ["P"]}},
    {"narration": "...", "reuse": "009_temple_mount_wide.png"}
  ],
  "short": [ ... cùng dạng ... ],
  "package": {
    "long":  {"title": "...", "description": "(bản đầy đủ cho YouTube)", "app_description": "(≤500 ký tự)", "hashtags": ["..."]},
    "short": {"title": "... #Shorts", "description": "...", "hashtags": ["Shorts", "..."]}
  },
  "sources": ["Mark 15:1-15", "Josephus, Antiquities 18.3", "..."]
}
```
Nhân vật dùng lâu dài (Judas, Jesus, Caiaphas, Pilate…) khai báo một lần trong `_tools/bf_style.py`; nhân vật chỉ có trong một tập thì khai trong `"characters"` của spec.

## 5. Mẹo ChatGPT Go
- Tạo ảnh tham chiếu (dòng 0) trước; mỗi chat mới tải nó lên + *"Use the attached image as the exact reference for [name]'s face, hair and clothing"*; ~8–10 ảnh/chat.
- Soát: lộ mặt Chúa Giêsu, hào quang, chữ tự sinh, bàn tay lỗi.


## 6. Cơ chế "repeat" trong beat (từ tập 3)
Một beat có thể `{"repeat": "<stem ảnh mới trong CHÍNH tập này>"}` để dùng lại một ảnh vừa tạo cho beat khác, thay vì luôn phải `new` hoặc `reuse` từ kho. Luật:
- Một ảnh dùng tối đa **3 lần** trong một video, và hai lần dùng phải **cách nhau ít nhất 3 beat** (không được lặp ở beat liền kề — nhìn giật). Nếu hai câu liền nhau tả cùng một cảnh, gộp chung thành một beat thay vì dùng `repeat` liền kề.
- 3 beat mở đầu luôn phải là `new`, không được `repeat` hay `reuse`.
- Công cụ tự kiểm tra hai điều trên khi chạy `prompts N`.
