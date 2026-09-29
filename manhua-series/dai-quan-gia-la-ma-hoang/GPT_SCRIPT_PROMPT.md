# Prompt dán cho GPT để viết kịch bản tập mới

Dùng khi muốn GPT (đọc trực tiếp link chương) viết kịch bản thay vì Claude đọc từng ảnh khung tranh —
tiết kiệm token Claude. Claude chỉ cần khớp câu vào khung tranh và dựng/render, không cần tự đọc hiểu
cả chương.

> ⚠️ **Cảnh báo thật (tập 13, 2026-09-29):** dán link cho GPT đã cho ra một script **bịa hoàn toàn** —
> đọc kỹ không khớp một chi tiết nào với ảnh chương thật (GPT tự chế ra cả một cảnh mua đồ không hề có).
> Nhiều khả năng manhuavn2.com/cotruyenday.com tải ảnh qua JS nên trình duyệt của GPT không thực sự thấy
> được tranh, dù có vẻ "đọc" được link. **Trước khi build, luôn nhờ Claude đối chiếu vài beat đầu với ảnh
> panel thật** (mở `_recap/sheets/sheet_01.jpg` so với beat đầu tiên) — nếu lệch hẳn thì dừng lại, đừng
> build tiếp. Cách chắc ăn hơn: chụp/upload trực tiếp ảnh `_recap/sheets/*.jpg` vào cửa sổ chat với GPT
> thay vì chỉ dán link, để GPT thực sự "nhìn" được tranh.

## Cách dùng

1. Copy toàn bộ prompt mẫu bên dưới.
2. Thay `<LINK CHƯƠNG>` bằng link chương thật (link chương lẻ trên manhuavn2.com/cotruyenday.com...).
3. Thay `<SỐ CHƯƠNG>` và `<TẬP TRƯỚC>` (tiêu đề tập ngay trước, để GPT viết đúng dòng link "◀ Tập...").
4. Dán vào GPT (bản có thể truy cập link, ví dụ ChatGPT có duyệt web).
5. GPT trả về đúng 1 khối JSON — gửi nguyên khối đó cho Claude, kèm câu kiểu:
   "đây là kịch bản chương N do GPT viết, khớp vào khung tranh và build giúp mình".
6. Claude sẽ: chạy `cut`/`sheets` (nếu chưa có), xem sheets một lượt để gán đúng `panel` (pNNN.jpg) cho
   từng beat, lưu thành `epNN/script.json`, rồi `build` + render + QA + cập nhật `SERIES.md`.

**Lưu ý:** JSON GPT trả về **chưa có** trường `panel` — đó là việc của Claude làm sau, dựa vào trường
`visual` (mô tả ngắn cảnh) mà GPT ghi kèm mỗi beat.

---

## Prompt mẫu

```
Bạn là biên kịch cho kênh YouTube Shorts review truyện tranh (manhua) tiếng Việt
"Đại Quản Gia Là Ma Hoàng". Đọc chương truyện tại link sau và viết kịch bản cho
video Short ~50-60 giây tóm tắt ĐÚNG một chương này:

<LINK CHƯƠNG>

Đây là chương <SỐ CHƯƠNG>.

BỐI CẢNH NHÂN VẬT ĐÃ DÙNG Ở CÁC TẬP TRƯỚC (giữ NGUYÊN cách viết tên, không đổi):
- Trác Nhất Phàm / Trác Phàm: nhân vật chính, Ma Hoàng (thủ lĩnh Bát Hoàng Thánh Vực) linh hồn
  nhập vào thân xác Trác Phàm, một gia nô của Lạc gia. Tâm ma khiến hắn buộc phải bảo vệ Lạc gia.
- Lạc Vân Thường: đại tiểu thư, đương gia Lạc gia.
- Lạc Vân Hải: thiếu gia Lạc gia.
- Bàng Diên / Bàng Vũ: thống lĩnh hộ vệ Lạc gia, trung thành.
- Triệu Thành: đệ tử phản bội (mục tiêu báo thù từ kiếp Ma Hoàng cũ).
- Ngự Hạ Thất Thế Gia: đại thế gia hùng mạnh, kẻ thù chính đang hình thành.
- U Minh Cốc: môn phái Ma Đạo, U Tuyền là đệ tử (đã chết ở chương 11, do chính Trác Phàm giết).
- Tiềm Long Các: thế lực trung lập/mập mờ, có Long Cửu (trưởng lão, "Cửu Thúc") và Long Kiệt
  (cháu, "A Kiệt") -- đang tạm đứng về phía bảo vệ Lạc gia (từ chương 12).
- Tôn gia: gia tộc đã đối đầu Lạc gia ở chương 11, liên quan tới Ngự Hạ Thất Thế Gia.
(Nếu chương mới có tên riêng chưa từng xuất hiện, tự thêm vào, giữ nguyên Hán-Việt hợp lý.)

CÔNG THỨC KỊCH BẢN CỦA KÊNH (bắt buộc theo đúng):
- Mở đầu bằng công thức "<Nhân vật> này" + một nghịch lý hiểu ngay trong một câu. KHÔNG chào hỏi,
  KHÔNG "hôm nay chúng ta sẽ xem...".
- Kết thúc bằng một cliffhanger (kết lửng) thật sự -- không giải quyết xong xuôi trong tập này,
  để kéo người xem sang tập sau.
- Xen 2-4 câu "bình luận kênh" (kind: "commentary") -- là góc nhìn/ý kiến CÁ NHÂN của người kể
  (khen/chê/đùa/soi), KHÔNG chỉ là kể lại nội dung bằng từ khác. Bắt buộc theo chính sách kiếm tiền
  YouTube (cấm video "chỉ đọc lại nội dung người khác", phải có bình luận/góc nhìn riêng).
- Văn phong: tiếng Việt, câu ngắn, nhanh, hơi hài hước, mỗi câu phải đẩy cốt truyện tới, không lặp ý,
  không thừa chữ.
- Tổng độ dài lời kể khoảng 280-310 âm tiết (khoảng 20-24 câu/beat) -- tương đương 55-60 giây khi đọc
  nhanh (~5.1 âm tiết/giây).
- Tên chương/nhân vật viết Hán-Việt, không phiên âm tiếng Trung.

XUẤT KẾT QUẢ ĐÚNG ĐỊNH DẠNG JSON SAU, KHÔNG THÊM CHỮ NÀO NGOÀI JSON (không markdown, không giải
thích trước/sau):

{
  "title": "Tiêu đề kết bằng !?, có nghịch lý, dưới 65 ký tự",
  "chapters": "<SỐ CHƯƠNG>",
  "description": "2-4 dòng: 1-2 câu tóm tắt nghịch lý của tập này (không spoil hết) + dòng 'Review truyện Đại Quản Gia Là Ma Hoàng – Tập <SỐ TẬP> (chương <SỐ CHƯƠNG>).' + dòng '◀ Tập <TẬP TRƯỚC SỐ>: <TẬP TRƯỚC TIÊU ĐỀ>'",
  "hashtags": ["#DaiQuanGiaLaMaHoang", "#ReviewManhua", "#Manhua", "#TuTien", "#XuyenKhong", "#ReviewTruyen"],
  "thumbnail": {
    "text": "1 câu ngắn tiếng Việt (dưới 25 ký tự), chữ to trên thumbnail",
    "prompt": "prompt TIẾNG ANH mô tả cảnh cao trào nhất của tập để vẽ ảnh thumbnail: phong cách manhua Trung Quốc, full-colour digital illustration, bold clean linework, cel shading, dramatic glow and rim light, vertical 9:16 composition, subject filling frame, leave top 25% darker/empty for title overlay, NO text, NO letters, NO speech bubbles, NO watermark"
  },
  "beats": [
    {"type": "HOOK", "kind": "recap", "narration": "Câu mở nghịch lý.", "visual": "mô tả rất ngắn (5-10 từ) cảnh nào trong chương, để sau này khớp đúng khung tranh"},
    {"type": "SETUP", "kind": "recap", "narration": "...", "visual": "..."},
    {"type": "BUILD", "kind": "recap", "narration": "...", "visual": "..."},
    {"type": "REVEAL", "kind": "commentary", "narration": "...", "visual": "..."},
    {"type": "ENDING", "kind": "recap", "narration": "Câu kết lửng.", "visual": "..."}
  ]
}

Lưu ý về "type" trong từng beat: HOOK (beat đầu tiên), SETUP, BUILD, REVEAL, REACTION, ENDING (beat
cuối cùng) -- dùng lần lượt theo diễn biến, không cần đều nhau. "kind" chỉ có 2 giá trị: "recap" (lời
kể) hoặc "commentary" (bình luận riêng, đọc bằng giọng khác trong video).
```

---

## Sau khi có JSON từ GPT

Gửi cho Claude nguyên khối JSON, kèm chỉ dẫn ngắn (ví dụ: "chương 13, nối tiếp tập 12"). Claude sẽ:

1. Kiểm tra ảnh chương đã tải (`manhua-recap/dqg_epNN`) chưa -- nếu chưa, tải qua trang `/manhua-fetch`
   trong app hoặc nhờ Claude chạy `recap.py fetch`.
2. `cut` + `sheets` như quy trình bình thường.
3. Xem qua sheets, gán trường `panel` (đúng file `pNNN.jpg`) cho từng beat dựa vào `visual` GPT ghi,
   xóa trường `visual` khỏi bản lưu cuối (không cần cho `build`).
4. Lưu thành `manhua-series/dai-quan-gia-la-ma-hoang/epNN/script.json`.
5. `build` + render + kiểm QA + cập nhật `SERIES.md`.

Bước tốn token nhất trước đây (Claude tự đọc hiểu cả chương, suy luận thoại, viết văn) chuyển hết
sang GPT. Việc còn lại của Claude (khớp panel, build, QA, ghi chép) rẻ hơn nhiều.
