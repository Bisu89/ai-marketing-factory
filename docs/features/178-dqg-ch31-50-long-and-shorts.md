# 178. Đại Quản Gia Là Ma Hoàng ch 31-50: 2 Long + 6 Short

Cùng cách làm như 177, từ `ep31..ep50/script.json` đã lưu. Cắt khung `dqgl_ep31..50`, ghép bằng script trong `long_31_40/`, `long_41_50/`, `short_g..l/`. Cả 8 video Final QA 100.

Commit: "feat: manhua-series -- Dai Quan Gia ch31-50 Long + 6 Short".

| Video | Chương | Độ dài | Project / job |
|---|---|---|---|
| Short G / H / I | 31-34 / 35-37 / 38-40 | 47.8s / 45.3s / 48.7s | 211-213 / 269-271 |
| Long | 31-40 | 13:16 | 214 / 272 |
| Short J / K / L | 41-44 / 45-47 / 48-50 | 45.9s / 44.8s / 47.3s | 215-217 / 274, 273, 275 |
| Long | 41-50 | 15:53 | 218 / 276 |

- Long 41-50 lần đầu FAILED ở GENERATING_VOICE (edge-tts chập chờn); `POST /factory-runs/{id}/retry` chạy lại là qua.
- Type beat lạ (TURN, CLIMAX, COMEDY...) được đổi về BUILD/REVEAL trước khi build.
- Khung chưa kiểm chứng bằng mắt.
