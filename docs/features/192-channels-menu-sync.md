# 192 — Channels menu: owned YouTube/Facebook channels + sync button

**Commit:** `feat(channels): owned-channel menu with per-channel sync button`

New `/channels` page ("Kênh & Lịch đăng") to track the channels the user publishes *to* (distinct from `app.models.Channel`, the source channels videos are downloaded from). Each channel is a card with followers/views/video count and an "Đồng bộ ngay" button (+ "Đồng bộ tất cả").

- Module `app/modules/channels/`: `owned_channel`, `channel_sync_run`, `channel_metric_daily` (one row per channel per day, overwritten by later syncs the same day — platforms only expose current totals, so history exists only because each sync is stored). Migration `0018`.
- YouTube sync = public channel statistics via a Data API key (no OAuth); Facebook = Graph API with a Page access token. Facebook total views/video count are stored as NULL (not exposed), shown as "—".
- Credentials are sent in headers, not the query string, because httpx logs full URLs at INFO (caught while testing: the key appeared in the log). `has_credential` is exposed, never the secret.
- A failed sync is recorded and shown on the card, not thrown; double-sync of one channel is rejected.
- Not built yet: scheduling, per-post analytics, OAuth, background auto-sync.
