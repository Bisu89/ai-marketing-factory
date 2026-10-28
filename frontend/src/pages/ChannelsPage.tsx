import { useCallback, useEffect, useState } from "react";
import { Loader2, Plus, RefreshCw, Trash2, Tv2 } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import {
  createChannel,
  deleteChannel,
  getChannelMetrics,
  listChannels,
  syncChannel,
  type ChannelMetric,
  type ChannelPlatform,
  type OwnedChannel,
} from "../api/channels";
import "./ChannelsPage.css";

const PLATFORM_LABEL: Record<ChannelPlatform, string> = { youtube: "YouTube", facebook: "Facebook Page" };

function num(value: number | null | undefined): string {
  return value == null ? "—" : value.toLocaleString("vi-VN");
}

function delta(latest: number | null | undefined, previous: number | null | undefined): string | null {
  if (latest == null || previous == null || latest === previous) return null;
  const d = latest - previous;
  return `${d > 0 ? "+" : ""}${d.toLocaleString("vi-VN")}`;
}

function ago(iso: string | null): string {
  if (!iso) return "chưa đồng bộ";
  // The API returns naive UTC timestamps; without a zone marker Date() would read them as local time.
  const t = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`).getTime();
  const mins = Math.max(0, Math.round((Date.now() - t) / 60000));
  if (mins < 1) return "vừa xong";
  if (mins < 60) return `${mins} phút trước`;
  if (mins < 60 * 24) return `${Math.round(mins / 60)} giờ trước`;
  return `${Math.round(mins / 1440)} ngày trước`;
}

function ChannelCard({
  channel,
  metrics,
  syncing,
  onSync,
  onDelete,
}: {
  channel: OwnedChannel;
  metrics: ChannelMetric[];
  syncing: boolean;
  onSync: () => void;
  onDelete: () => void;
}) {
  const latest = metrics[metrics.length - 1];
  const previous = metrics[metrics.length - 2];
  const followerLabel = channel.platform === "youtube" ? "Subscribers" : "Followers";
  return (
    <div className="ch-card">
      <div className="ch-card-head">
        <div>
          <div className="ch-card-name">{channel.name}</div>
          <div className="ch-card-sub">
            <span className={`ch-badge ch-badge-${channel.platform}`}>{PLATFORM_LABEL[channel.platform]}</span>
            <span className="ch-muted">{channel.external_id}</span>
          </div>
        </div>
        <button className="btn btn-secondary" onClick={onDelete} title="Xoá kênh" disabled={syncing}>
          <Trash2 size={14} />
        </button>
      </div>

      <div className="ch-stats">
        <div>
          <div className="ch-stat-label">{followerLabel}</div>
          <div className="ch-stat-value">{num(latest?.followers)}</div>
          {delta(latest?.followers, previous?.followers) && (
            <div className="ch-stat-delta">{delta(latest?.followers, previous?.followers)} so với lần trước</div>
          )}
        </div>
        <div>
          <div className="ch-stat-label">Tổng views</div>
          <div className="ch-stat-value">{num(latest?.total_views)}</div>
        </div>
        <div>
          <div className="ch-stat-label">Số video</div>
          <div className="ch-stat-value">{num(latest?.video_count)}</div>
        </div>
      </div>

      {channel.last_sync_status === "error" && <div className="ch-error">{channel.last_sync_message}</div>}

      <div className="ch-card-foot">
        <span className="ch-muted">Đồng bộ cuối: {ago(channel.last_synced_at)}</span>
        <button className="btn btn-primary" onClick={onSync} disabled={syncing}>
          {syncing ? <Loader2 size={14} className="spin" /> : <RefreshCw size={14} />}
          Đồng bộ ngay
        </button>
      </div>
    </div>
  );
}

export function ChannelsPage() {
  const [channels, setChannels] = useState<OwnedChannel[]>([]);
  const [metrics, setMetrics] = useState<Record<number, ChannelMetric[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncingIds, setSyncingIds] = useState<Set<number>>(new Set());

  const [adding, setAdding] = useState(false);
  const [platform, setPlatform] = useState<ChannelPlatform>("youtube");
  const [name, setName] = useState("");
  const [externalId, setExternalId] = useState("");
  const [credential, setCredential] = useState("");
  const [saving, setSaving] = useState(false);

  const reload = useCallback(async () => {
    const rows = await listChannels();
    setChannels(rows);
    const entries = await Promise.all(rows.map(async (c) => [c.id, await getChannelMetrics(c.id)] as const));
    setMetrics(Object.fromEntries(entries));
  }, []);

  useEffect(() => {
    reload()
      .catch((err) => setError(err instanceof Error ? err.message : "Không tải được danh sách kênh."))
      .finally(() => setLoading(false));
  }, [reload]);

  async function runSync(id: number) {
    setSyncingIds((s) => new Set(s).add(id));
    setError(null);
    try {
      await syncChannel(id);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đồng bộ thất bại.");
    } finally {
      setSyncingIds((s) => {
        const next = new Set(s);
        next.delete(id);
        return next;
      });
    }
  }

  async function syncAll() {
    await Promise.all(channels.map((c) => runSync(c.id)));
  }

  async function handleAdd() {
    setSaving(true);
    setError(null);
    try {
      const created = await createChannel({
        platform,
        name: name.trim() || externalId.trim(),
        external_id: externalId.trim(),
        credential: credential.trim() || undefined,
      });
      setAdding(false);
      setName("");
      setExternalId("");
      setCredential("");
      await reload();
      if (created.has_credential) void runSync(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thêm được kênh.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(c: OwnedChannel) {
    if (!window.confirm(`Xoá kênh "${c.name}" và toàn bộ số liệu đã lưu?`)) return;
    try {
      await deleteChannel(c.id);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không xoá được kênh.");
    }
  }

  const credentialLabel = platform === "youtube" ? "YouTube Data API key" : "Page access token";
  const idLabel = platform === "youtube" ? "Channel ID (bắt đầu bằng UC…)" : "Page ID";

  return (
    <>
      <PageHeader
        title="Kênh & Lịch đăng"
        subtitle="Quản lý từng kênh YouTube / Facebook Page và số liệu tích luỹ theo ngày. Số liệu chỉ cập nhật khi app đang chạy và bạn bấm đồng bộ."
        actions={
          <>
            <button className="btn btn-secondary" onClick={syncAll} disabled={channels.length === 0 || syncingIds.size > 0}>
              <RefreshCw size={14} /> Đồng bộ tất cả
            </button>
            <button className="btn btn-primary" onClick={() => setAdding((v) => !v)}>
              <Plus size={14} /> Thêm kênh
            </button>
          </>
        }
      />

      {error && <div className="ch-alert">{error}</div>}

      {adding && (
        <div className="ch-form">
          <label>
            Nền tảng
            <select value={platform} onChange={(e) => setPlatform(e.target.value as ChannelPlatform)}>
              <option value="youtube">YouTube</option>
              <option value="facebook">Facebook Page</option>
            </select>
          </label>
          <label>
            Tên hiển thị (để trống = lấy từ nền tảng)
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label>
            {idLabel}
            <input value={externalId} onChange={(e) => setExternalId(e.target.value)} />
          </label>
          <label>
            {credentialLabel}
            <input type="password" value={credential} onChange={(e) => setCredential(e.target.value)} autoComplete="off" />
          </label>
          <div className="ch-form-actions">
            <button className="btn btn-secondary" onClick={() => setAdding(false)}>
              Huỷ
            </button>
            <button className="btn btn-primary" onClick={handleAdd} disabled={saving || !externalId.trim()}>
              {saving && <Loader2 size={14} className="spin" />} Lưu
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="ch-loading">
          <Loader2 size={20} className="spin" />
        </div>
      ) : channels.length === 0 ? (
        <EmptyState
          icon={Tv2}
          title="Chưa có kênh nào"
          description="Bấm “Thêm kênh”, nhập ID kênh và API key/token để bắt đầu theo dõi số liệu."
        />
      ) : (
        <div className="ch-grid">
          {channels.map((c) => (
            <ChannelCard
              key={c.id}
              channel={c}
              metrics={metrics[c.id] ?? []}
              syncing={syncingIds.has(c.id)}
              onSync={() => void runSync(c.id)}
              onDelete={() => void handleDelete(c)}
            />
          ))}
        </div>
      )}
    </>
  );
}
