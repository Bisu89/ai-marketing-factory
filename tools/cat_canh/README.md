# Cat Canh — cắt video thành các cảnh (scene)

Tool độc lập, không phụ thuộc backend/frontend của AI Content Library. Dùng
[PySceneDetect](https://scenedetect.com/) để tự động phát hiện điểm chuyển
cảnh và xuất mỗi cảnh thành 1 file video riêng (qua ffmpeg).

## Cài đặt

```
pip install -r requirements.txt
```

Cần có `ffmpeg` trong PATH.

## Dùng

Chạy không tham số để mở menu tương tác (nhập đường dẫn video, ngưỡng nhạy,
độ dài cảnh tối thiểu, trim, thư mục lưu — có giá trị mặc định sẵn):

```
python cat_canh.py
```

Hoặc dùng trực tiếp qua dòng lệnh (không mở menu) như bản gốc:

```
python cat_canh.py video.mp4
python cat_canh.py video.mp4 --do-nhay 27 --thu-muc ket_qua
python cat_canh.py video.mp4 --canh-toi-thieu 1.0 --trim 0.15
```

| Tham số | Ý nghĩa | Mặc định |
|---|---|---|
| `video` | Đường dẫn file video đầu vào | — |
| `--do-nhay` | Ngưỡng phát hiện chuyển cảnh (nhỏ hơn = nhạy hơn, cắt nhiều cảnh hơn) | 46 |
| `--canh-toi-thieu` | Độ dài tối thiểu 1 cảnh (giây) | 0.6 |
| `--thu-muc` | Thư mục lưu kết quả | `<tên_video>_canh` |
| `--trim` | Cắt bớt đầu/cuối mỗi cảnh (giây) — chỉ bật khi video có hiệu ứng chuyển cảnh mềm (dissolve/crossfade) | 0 (tắt) |

Đã kiểm tra thật: dựng video test 3 cảnh màu bằng ffmpeg, chạy cả chế độ menu
và chế độ CLI cũ, xác nhận cắt đúng số cảnh và file output hợp lệ.
