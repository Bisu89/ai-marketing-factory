# Ảnh AI cho phim tài liệu — phong cách Baroque (lấy từ Biblical Figures) + chiến lược kết hợp

Khối prompt gốc nằm ở `biblical-figures-prompts/_tools/bf_style.py` (`LONG_STYLE`, tiếng Anh, 16:9). Ở đây là bản **đã
điều chỉnh cho phim lịch sử không tôn giáo**: bỏ các ràng buộc riêng của tranh tôn giáo (halo, tia sáng thần thánh), thay
mô tả thời kỳ bằng chỗ trống `{ERA}`.

## 1. Khi nào dùng ảnh nào
| Cảnh cần | Dùng |
|---|---|
| Chân dung nhân vật có thật | **Ảnh tư liệu thật** (chân dung/tượng/đồng xu/bản khắc cổ). Không để AI bịa mặt |
| Sự kiện/trận đánh nổi tiếng đã có tranh | Tranh cổ miền công cộng (Commons) |
| Vật thể, khung cảnh, công việc (xưởng đúc pháo, bức tường, bến cảng, đoàn quân từ xa) | **Ảnh AI Baroque** |
| Số liệu, năm, bằng chứng, tiêu đề, bản đồ | Không cần ảnh — cảnh đồ họa do Remotion vẽ |

## 2. Khối phong cách (dán nguyên vào cuối mỗi prompt)

```
Aged oil painting in the style of 17th-century Baroque old-master history painting (Caravaggio, Rembrandt), rich visible
brushstrokes, fine craquelure and slightly worn varnish texture, warm sepia, umber and ochre palette with deep brown
shadows, dramatic candlelit chiaroscuro, soft painterly edges, period-accurate {ERA} clothing, armor and architecture,
museum masterpiece quality. Wide landscape composition framed for a 16:9 crop: keep the main subject in the central
horizontal band, nothing important near the top or bottom edges. IMPORTANT STYLE RESTRICTIONS: a painting, not a
photograph, not photorealistic, not a 3D render, not modern digital art, not anime, no modern objects, no blood, no gore,
no wounds, no corpses, no text, no letters, no signature, no captions, no watermark, no picture frame, no border.
```

`{ERA}` ví dụ: `15th-century Byzantine and Ottoman` · `first-century Roman` · `medieval Viking-age Scandinavian`.
Vì cảnh được đóng khung bởi chữ/phụ đề ở đáy: **để dải thấp của khung trống, chủ thể ở dải giữa**.

## 3. Công thức prompt một cảnh
```
<chủ thể và hành động cụ thể>, <bối cảnh/thời điểm trong ngày>, <ánh sáng>; <chi tiết thời kỳ>; faces turned away,
in deep shadow or seen from far away. <KHỐI PHONG CÁCH ở mục 2>
```
- Viết **cụ thể và hẹp** (một chủ thể rõ), tránh đám đông cận mặt (AI hay vẽ mặt hỏng/lặp).
- Luôn có `faces turned away / in shadow / from far away` cho cảnh người thật.
- Không đề cập tên người thật nếu không cần; mô tả vai trò ("một kỹ sư đúc pháo", "lính gác trên tường thành").
- Cả loạt dùng **cùng một khối phong cách** và cùng `{ERA}` để đồng nhất.

### Ví dụ (tập Constantinople 1453, 4 ảnh AI cho cảnh chưa có tư liệu)
1. **Hook — thành phố bị vây**: `Constantinople at dusk under siege, the great dome of Hagia Sophia and the tall land walls
   silhouetted against a smoky orange sky, hundreds of Ottoman campfires and tents glowing on the plain in the foreground,
   tiny distant figures on the ramparts; faces never visible.` + khối phong cách
2. **Tường thành**: `The massive double land walls of Constantinople with towers and a dry moat seen from outside at golden
   hour, weathered stone, defenders' banners barely visible on the battlements, an empty road in the foreground; no people
   in close view.` + khối phong cách
3. **Xưởng đúc pháo (Orban)**: `A dim 15th-century foundry workshop where bronze workers pour glowing molten metal into a
   huge clay mould for an enormous bombard, sparks and steam in the dark, silhouettes with faces in deep shadow.` + khối phong cách
4. **Pháo bắn vào tường**: `An enormous bronze bombard on a heavy wooden carriage aimed at the ancient walls, a cloud of
   smoke and dust, gunners as dark silhouettes at dawn, the walls cracking in the haze; faces not visible.` + khối phong cách

## 4. Quy trình CSV (không gọi API)
1. Trong app: tab **Ảnh → Tính danh sách ảnh cần tạo → Tải CSV prompt** (cột: STT, Ten file, Tags, Prompt đầy đủ).
2. Prompt tự sinh chỉ lấy câu đầu của lời dẫn + dòng phong cách chung → **thay bằng prompt viết tay theo mục 3** (sửa ở tab
   Storyboard, ô "Mô tả hình ảnh / prompt"; sau khi sửa, ảnh cũ của cảnh đó tự bị đánh dấu lỗi thời).
3. Tạo ảnh ở ChatGPT/công cụ của bạn; **đặt tên file bắt đầu bằng mã cảnh** (`S003_walls.png`), 16:9.
4. Tab Ảnh → Nhập thư mục → xem từng ảnh → **duyệt/từ chối** (kiểm tra sai lịch sử: trang phục, vũ khí, kiến trúc).
5. Ghi nhãn "Minh họa AI": thêm dòng chữ `caption` "Minh họa AI" ở tab Storyboard cho cảnh đó (xem việc tiếp theo trong `HANDOFF.md`
   — chưa tự động).

## 5. Lỗi hay gặp ở ảnh AI lịch sử (soát khi duyệt)
Trang phục/mũ giáp sai thời kỳ · súng/đại bác sai kiểu · kiến trúc hiện đại lẫn vào · chữ giả/ký hiệu vô nghĩa trên cờ,
tường · đám đông mặt méo · cùng một mặt lặp lại · màu quá rực (không đúng giọng sepia/umber).
