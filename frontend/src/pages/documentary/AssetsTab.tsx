import { useState } from "react";
import { Check, Copy, Download, FolderOpen, Upload, X } from "lucide-react";
import {
  approveAsset,
  assetFileUrl,
  assignAsset,
  csvDownloadUrl,
  exportImageCsv,
  getGateReview,
  importAsset,
  importImageFolder,
  listAssets,
  listScenes,
  patchAsset,
  rejectAsset,
} from "../../api/documentary";
import type { Asset, Scene } from "../../api/documentary";
import { FolderBrowserModal } from "../../components/FolderBrowserModal";
import { ActionFeedback, Badge, Busy, Field, Loading, Notice, ReviewBox, useAction, useLoader } from "./shared";
import type { TabProps } from "./shared";
import { ASSET_STATE_VI } from "./StoryboardTab";

const ORIGIN_VI: Record<Asset["origin"], string> = {
  imported: "Ảnh tự nhập",
  archival: "Ảnh tư liệu",
  ai_manual: "AI (bạn tự tạo)",
};

function thumbUrl(projectId: number, a: Asset) {
  return `${assetFileUrl(projectId, a.id)}?h=${a.content_hash.slice(0, 8)}`;
}

function LicenseBox({ asset, projectId, onDone }: { asset: Asset; projectId: number; onDone: () => void }) {
  const { busy, error, run } = useAction();
  const [lic, setLic] = useState(asset.license ?? "");
  const [attr, setAttr] = useState(asset.attribution ?? "");
  const [url, setUrl] = useState(asset.source_url ?? "");
  return (
    <div className="doc-item" style={{ background: "var(--surface-alt)" }}>
      <div className="doc-muted">Ảnh tư liệu cần ghi rõ giấy phép và nguồn trước khi duyệt — ảnh công khai trên mạng không mặc định được dùng thương mại.</div>
      {error && <Notice kind="error">{error}</Notice>}
      <Field label="Giấy phép (VD: Public domain, CC BY 4.0)">
        <input value={lic} onChange={(e) => setLic(e.target.value)} />
      </Field>
      <Field label="Tác giả / nguồn ghi công">
        <input value={attr} onChange={(e) => setAttr(e.target.value)} />
      </Field>
      <Field label="URL nguồn">
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" />
      </Field>
      <button
        className="btn doc-btn-sm"
        style={{ alignSelf: "flex-start" }}
        disabled={busy !== null}
        onClick={async () => (await run("lic", () => patchAsset(projectId, asset.id, { license: lic, attribution: attr, source_url: url }))) && onDone()}
      >
        Lưu thông tin bản quyền
      </button>
    </div>
  );
}

function ReplaceBox({ projectId, head, assets, onDone }: { projectId: number; head: Scene; assets: Asset[]; onDone: () => void }) {
  const { busy, error, run } = useAction();
  const [path, setPath] = useState("");
  const [origin, setOrigin] = useState<"imported" | "archival">("imported");
  const [lic, setLic] = useState("");
  const [attr, setAttr] = useState("");
  const [url, setUrl] = useState("");
  const others = assets.filter((a) => a.id !== head.asset_id && a.approval_status !== "rejected");

  return (
    <details>
      <summary className="doc-muted" style={{ cursor: "pointer" }}>
        Thay / gán ảnh khác
      </summary>
      <div className="doc-list" style={{ marginTop: 8 }}>
        {error && <Notice kind="error">{error}</Notice>}
        {others.length > 0 && (
          <Field label="Dùng ảnh có sẵn trong kho">
            <select
              value=""
              disabled={busy !== null}
              onChange={async (e) => {
                if (!e.target.value) return;
                (await run("assign", () => assignAsset(projectId, head.id, Number(e.target.value)))) && onDone();
              }}
            >
              <option value="">— chọn ảnh #id —</option>
              {others.map((a) => (
                <option key={a.id} value={a.id}>
                  #{a.id} · {ORIGIN_VI[a.origin]} · {a.width}×{a.height} · {a.approval_status === "approved" ? "đã duyệt" : "chờ duyệt"}
                </option>
              ))}
            </select>
          </Field>
        )}
        <Field label="…hoặc nhập file ảnh từ máy (đường dẫn đầy đủ)">
          <input value={path} onChange={(e) => setPath(e.target.value)} placeholder="C:\Users\bạn\Pictures\anh.png" />
        </Field>
        <div className="doc-row">
          <Field label="Loại ảnh">
            <select value={origin} onChange={(e) => setOrigin(e.target.value as "imported" | "archival")}>
              <option value="imported">Ảnh tự nhập (ảnh của bạn)</option>
              <option value="archival">Ảnh tư liệu (có giấy phép/nguồn)</option>
            </select>
          </Field>
        </div>
        {origin === "archival" && (
          <div className="doc-row">
            <Field label="Giấy phép">
              <input value={lic} onChange={(e) => setLic(e.target.value)} />
            </Field>
            <Field label="Tác giả / ghi công">
              <input value={attr} onChange={(e) => setAttr(e.target.value)} />
            </Field>
            <Field label="URL nguồn">
              <input value={url} onChange={(e) => setUrl(e.target.value)} />
            </Field>
          </div>
        )}
        <div className="doc-actions">
          <button
            className="btn doc-btn-sm"
            disabled={busy !== null || !path.trim()}
            onClick={async () => {
              const a = await run("import", () =>
                importAsset(projectId, { path: path.trim(), origin, license: lic || undefined, attribution: attr || undefined, source_url: url || undefined }),
              );
              if (!a) return;
              (await run("assign", () => assignAsset(projectId, head.id, a.id))) && (setPath(""), onDone());
            }}
          >
            <Upload size={13} /> Nhập & gán cho nhóm này
          </button>
          {head.asset_id !== null && (
            <button
              className="btn doc-btn-sm doc-btn-danger"
              disabled={busy !== null}
              onClick={async () => (await run("unassign", () => assignAsset(projectId, head.id, null))) && onDone()}
            >
              Gỡ ảnh khỏi nhóm
            </button>
          )}
        </div>
      </div>
    </details>
  );
}

export function AssetsTab({ project, reloadProject }: TabProps) {
  const id = project.id;
  const stamp = `${id}:${project.updated_at}`;
  const scenes = useLoader(() => listScenes(id), stamp);
  const assets = useLoader(() => listAssets(id), stamp);
  const review = useLoader(() => getGateReview(id, "storyboard_assets"), stamp);
  const { busy, error, info, run } = useAction();
  const [csvInfo, setCsvInfo] = useState<{ to_generate: number; reused_from_cache: number } | null>(null);
  const [folder, setFolder] = useState("");
  const [pickFolder, setPickFolder] = useState(false);
  const [report, setReport] = useState<Awaited<ReturnType<typeof importImageFolder>> | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  const refresh = () => {
    void scenes.reload();
    void assets.reload();
    void review.reload();
    reloadProject();
  };

  if (scenes.loading || assets.loading) return <Loading />;
  const sceneList = scenes.data ?? [];
  const assetList = assets.data ?? [];
  const byId = new Map(assetList.map((a) => [a.id, a]));
  const heads = sceneList.filter((s) => s.asset_strategy === "image" && s.image_group === s.scene_key);
  const used = new Set(sceneList.map((s) => s.asset_id).filter((x): x is number => x !== null));
  const unassigned = assetList.filter((a) => !used.has(a.id));
  const programmatic = sceneList.filter((s) => s.asset_strategy === "programmatic").length;

  async function copy(text: string, key: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
      window.setTimeout(() => setCopied(null), 1500);
    } catch {
      /* clipboard unavailable: the prompt is still visible on screen */
    }
  }

  return (
    <div className="doc-page">
      <ActionFeedback error={error ?? scenes.error ?? assets.error} info={info} />

      {sceneList.length === 0 ? (
        <Notice kind="info">Chưa có storyboard. Hãy lập storyboard ở tab “Storyboard” trước.</Notice>
      ) : (
        <>
          <div className="doc-card">
            <h3>Tạo ảnh bằng tay (không gọi API)</h3>
            <p className="doc-muted">
              {heads.length} nhóm ảnh cần hình, {programmatic} cảnh dùng đồ họa lập trình (không cần ảnh). Ảnh đã duyệt có cùng mô tả sẽ được dùng lại,
              chỉ phần còn thiếu mới vào CSV.
            </p>
            <div className="doc-actions">
              <button
                className="btn btn-primary doc-btn-sm"
                disabled={busy !== null}
                onClick={async () => {
                  const r = await run("csv", () => exportImageCsv(id));
                  if (r) {
                    setCsvInfo(r);
                    refresh();
                  }
                }}
              >
                Tính danh sách ảnh cần tạo
              </button>
              {csvInfo && (
                <>
                  <span>
                    <strong>{csvInfo.to_generate}</strong> ảnh cần tạo
                    {csvInfo.reused_from_cache > 0 && `, ${csvInfo.reused_from_cache} nhóm dùng lại ảnh cũ`}
                  </span>
                  {csvInfo.to_generate > 0 && (
                    <a className="btn doc-btn-sm" href={csvDownloadUrl(id)}>
                      <Download size={13} /> Tải CSV prompt
                    </a>
                  )}
                </>
              )}
            </div>
            <p className="doc-muted">
              Tạo ảnh theo CSV, <strong>đặt tên file bắt đầu bằng mã cảnh</strong> (VD <code>S003_hook.png</code>), bỏ vào một thư mục rồi nhập bên dưới.
            </p>
            <div className="doc-row">
              <Field label="Thư mục chứa ảnh đã tạo">
                <input value={folder} onChange={(e) => setFolder(e.target.value)} placeholder="C:\…\anh_da_tao" />
              </Field>
              <button className="btn doc-btn-sm" onClick={() => setPickFolder(true)}>
                <FolderOpen size={13} /> Chọn thư mục
              </button>
              <button
                className="btn btn-primary doc-btn-sm"
                disabled={busy !== null || !folder.trim()}
                onClick={async () => {
                  const r = await run("folder", () => importImageFolder(id, folder.trim()));
                  if (r) {
                    setReport(r);
                    refresh();
                  }
                }}
              >
                <Upload size={13} /> Nhập thư mục
              </button>
              {busy === "folder" && <Busy />}
            </div>
            {report && (
              <Notice kind={report.failed.length || report.unmatched.length ? "warn" : "ok"}>
                Đã nhập {report.imported.length} ảnh
                {report.duplicate.length > 0 && `, ${report.duplicate.length} ảnh trùng nội dung (dùng lại)`}
                {report.unmatched.length > 0 && `; ${report.unmatched.length} file không khớp mã cảnh nào: ${report.unmatched.join(", ")}`}
                {report.failed.length > 0 && `; lỗi: ${report.failed.map((f) => `${f.file} (${f.reason})`).join("; ")}`}. Ảnh mới ở trạng thái “chờ duyệt”.
              </Notice>
            )}
          </div>

          <div className="doc-card">
            <h3>Contact sheet — duyệt ảnh</h3>
            {heads.length === 0 && <p className="doc-muted">Mọi cảnh đều là đồ họa lập trình, không có ảnh cần duyệt.</p>}
            <div className="doc-grid">
              {heads.map((h) => {
                const a = h.asset_id !== null ? byId.get(h.asset_id) : undefined;
                const members = sceneList.filter((s) => s.image_group === h.scene_key);
                const st = ASSET_STATE_VI[h.asset_state];
                return (
                  <div key={h.id} className="doc-item">
                    {a ? (
                      <img className="doc-thumb" src={thumbUrl(id, a)} alt={`Ảnh cho ${h.scene_key}`} loading="lazy" />
                    ) : (
                      <div className="doc-thumb doc-thumb-empty">Chưa có ảnh</div>
                    )}
                    <div className="doc-item-head">
                      <strong>{members.map((m) => m.scene_key).join(", ")}</strong>
                      <span className="grow" />
                      <Badge tone={st.tone}>{st.label}</Badge>
                    </div>
                    {a && (
                      <div className="doc-muted">
                        {ORIGIN_VI[a.origin]} · {a.width}×{a.height}
                        {a.origin === "archival" && ` · ${a.license || "chưa ghi giấy phép"}`}
                      </div>
                    )}
                    <div className="doc-muted" style={{ maxHeight: 64, overflow: "auto" }}>
                      {h.visual_objective}
                    </div>
                    <div className="doc-actions">
                      <button className="btn doc-btn-sm" onClick={() => void copy(h.visual_objective, h.scene_key)}>
                        <Copy size={12} /> {copied === h.scene_key ? "Đã chép" : "Chép prompt"}
                      </button>
                      {a && a.approval_status !== "approved" && h.asset_state !== "stale" && (
                        <button
                          className="btn doc-btn-sm btn-primary"
                          disabled={busy !== null}
                          onClick={async () => (await run("approve", () => approveAsset(id, a.id))) && refresh()}
                        >
                          <Check size={13} /> Duyệt
                        </button>
                      )}
                      {a && a.approval_status !== "rejected" && (
                        <button
                          className="btn doc-btn-sm doc-btn-danger"
                          disabled={busy !== null}
                          onClick={async () => (await run("reject", () => rejectAsset(id, a.id))) && refresh()}
                        >
                          <X size={13} /> Từ chối
                        </button>
                      )}
                    </div>
                    {h.asset_state === "stale" && (
                      <div className="doc-issue-warn">Mô tả cảnh đã đổi sau khi ảnh được tạo — hãy tạo lại ảnh hoặc thay ảnh khác.</div>
                    )}
                    {a && a.origin === "archival" && <LicenseBox asset={a} projectId={id} onDone={refresh} />}
                    <ReplaceBox projectId={id} head={h} assets={assetList} onDone={refresh} />
                  </div>
                );
              })}
            </div>
          </div>

          {unassigned.length > 0 && (
            <div className="doc-card">
              <h3>Ảnh trong kho chưa gán cho cảnh nào ({unassigned.length})</h3>
              <div className="doc-grid">
                {unassigned.map((a) => (
                  <div key={a.id} className="doc-item">
                    <img className="doc-thumb" src={thumbUrl(id, a)} alt={`Ảnh #${a.id}`} loading="lazy" />
                    <div className="doc-muted">
                      #{a.id} · {ORIGIN_VI[a.origin]} · {a.approval_status === "approved" ? "đã duyệt" : a.approval_status === "rejected" ? "bị từ chối" : "chờ duyệt"}
                    </div>
                    {a.origin === "archival" && <LicenseBox asset={a} projectId={id} onDone={refresh} />}
                    <div className="doc-actions">
                      {a.approval_status !== "approved" && (
                        <button className="btn doc-btn-sm btn-primary" disabled={busy !== null} onClick={async () => (await run("approve", () => approveAsset(id, a.id))) && refresh()}>
                          <Check size={13} /> Duyệt
                        </button>
                      )}
                      {a.approval_status !== "rejected" && (
                        <button className="btn doc-btn-sm doc-btn-danger" disabled={busy !== null} onClick={async () => (await run("reject", () => rejectAsset(id, a.id))) && refresh()}>
                          <X size={13} /> Từ chối
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <ReviewBox review={review.data} title="Kiểm tra cổng 3" />
        </>
      )}

      {pickFolder && (
        <FolderBrowserModal
          initialPath={folder || undefined}
          onSelect={(p) => {
            setFolder(p);
            setPickFolder(false);
          }}
          onClose={() => setPickFolder(false)}
        />
      )}
    </div>
  );
}
