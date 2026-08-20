import { useEffect, useState } from "react";
import { Loader2, Plus, RefreshCw, Sparkles, Trash2 } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import {
  createLink,
  createProduct,
  deleteLink,
  deleteProduct,
  getAffiliateKpi,
  getLinks,
  getProducts,
  recommendProducts,
  recomputeProductScore,
} from "../api/affiliate";
import { config } from "../config/env";
import type { AffiliateKPI, AffiliateLink, AffiliateProduct, ProductMatch } from "../types/affiliate";
import "./AffiliatePage.css";

const REDIRECT_BASE = config.apiBaseUrl.replace(/\/api\/v1\/?$/, "");

function usd(value: number | null): string {
  return value == null ? "—" : `$${value.toFixed(2)}`;
}

function emptyForm() {
  return { name: "", category: "", affiliate_url: "", platform: "", price: "", commission_rate: "", rating: "", tags: "" };
}

function ProductLinks({ product }: { product: AffiliateProduct }) {
  const [links, setLinks] = useState<AffiliateLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [label, setLabel] = useState("");

  function refresh() {
    getLinks(product.id)
      .then(setLinks)
      .finally(() => setLoading(false));
  }

  useEffect(refresh, [product.id]);

  async function handleCreate() {
    await createLink(product.id, label.trim() || null);
    setLabel("");
    refresh();
  }

  async function handleDelete(id: number) {
    await deleteLink(id);
    refresh();
  }

  if (loading) return <Loader2 size={14} className="spin" />;

  return (
    <div className="af-links">
      <div className="af-links-form">
        <input className="af-input" placeholder="Nhãn link (vd: TikTok bio)" value={label} onChange={(e) => setLabel(e.target.value)} />
        <button className="btn btn-secondary" onClick={handleCreate}>
          <Plus size={13} /> Tạo link
        </button>
      </div>
      {links.length === 0 ? (
        <p className="af-hint">Chưa có link nào.</p>
      ) : (
        <ul className="af-link-list">
          {links.map((l) => (
            <li key={l.id}>
              <code>{`${REDIRECT_BASE}/r/${l.link_code}`}</code>
              <span>{l.label || "(không nhãn)"}</span>
              <span className="af-click-count">{l.click_count} clicks</span>
              <button className="btn btn-secondary" onClick={() => handleDelete(l.id)}>
                <Trash2 size={12} />
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="af-hint">
        Link chỉ thực sự đếm click khi nơi đăng (TikTok bio, mô tả video...) có thể gọi tới backend này -- với chế độ
        chạy local mặc định, chỉ hoạt động trên chính máy này. Cần expose backend công khai (reverse proxy/tunnel) để
        dùng thật ngoài đời.
      </p>
    </div>
  );
}

export function AffiliatePage() {
  const [kpi, setKpi] = useState<AffiliateKPI | null>(null);
  const [products, setProducts] = useState<AffiliateProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [form, setForm] = useState(emptyForm());
  const [creating, setCreating] = useState(false);
  const [recomputingId, setRecomputingId] = useState<number | null>(null);

  const [storyText, setStoryText] = useState("");
  const [matching, setMatching] = useState(false);
  const [matches, setMatches] = useState<ProductMatch[] | null>(null);
  const [matchError, setMatchError] = useState<string | null>(null);

  function refresh() {
    setLoading(true);
    Promise.all([getAffiliateKpi(), getProducts()])
      .then(([k, p]) => {
        setKpi(k);
        setProducts(p);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Không tải được dữ liệu Affiliate."))
      .finally(() => setLoading(false));
  }

  useEffect(refresh, []);

  async function handleCreateProduct() {
    if (!form.name.trim() || !form.category.trim() || !form.affiliate_url.trim() || !form.platform.trim() || creating) return;
    setCreating(true);
    setError(null);
    try {
      await createProduct({
        name: form.name.trim(),
        category: form.category.trim(),
        affiliate_url: form.affiliate_url.trim(),
        platform: form.platform.trim(),
        price: form.price.trim() ? Number(form.price) : null,
        commission_rate: form.commission_rate.trim() ? Number(form.commission_rate) : null,
        rating: form.rating.trim() ? Number(form.rating) : null,
        tags: form.tags.trim() ? form.tags.split(",").map((t) => t.trim()).filter(Boolean) : null,
      });
      setForm(emptyForm());
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tạo được sản phẩm.");
    } finally {
      setCreating(false);
    }
  }

  async function handleDeleteProduct(id: number) {
    if (!window.confirm("Xoá sản phẩm này?")) return;
    await deleteProduct(id);
    refresh();
  }

  async function handleRecompute(id: number) {
    setRecomputingId(id);
    try {
      await recomputeProductScore(id);
      refresh();
    } finally {
      setRecomputingId(null);
    }
  }

  async function handleMatch() {
    if (!storyText.trim() || matching) return;
    setMatching(true);
    setMatchError(null);
    setMatches(null);
    try {
      const result = await recommendProducts({ story_text: storyText.trim() });
      setMatches(result);
    } catch (err) {
      setMatchError(err instanceof Error ? err.message : "Không đề xuất được sản phẩm.");
    } finally {
      setMatching(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Affiliate Engine"
        subtitle="Content → Audience → Product Category → Product → Affiliate Link → Click → Order → Commission. Chỉ đề xuất, không tự động gắn vào story nào."
      />

      {error && <div className="af-alert af-alert-error">{error}</div>}

      {kpi && (
        <div className="af-kpis">
          <div className="af-kpi">
            <div className="af-kpi-value">{kpi.total_clicks.toLocaleString("vi-VN")}</div>
            <div className="af-kpi-label">Clicks ({kpi.real_tracked_clicks} thật + {kpi.manual_clicks} nhập tay)</div>
          </div>
          <div className="af-kpi">
            <div className="af-kpi-value">{kpi.total_orders.toLocaleString("vi-VN")}</div>
            <div className="af-kpi-label">Orders</div>
          </div>
          <div className="af-kpi">
            <div className="af-kpi-value">{usd(kpi.total_gmv_usd)}</div>
            <div className="af-kpi-label">GMV {kpi.gmv_excluded_orders > 0 && `(thiếu giá ${kpi.gmv_excluded_orders} order)`}</div>
          </div>
          <div className="af-kpi">
            <div className="af-kpi-value">{usd(kpi.total_commission_usd)}</div>
            <div className="af-kpi-label">Commission</div>
          </div>
          <div className="af-kpi">
            <div className="af-kpi-value">{kpi.revenue_per_1000_views_usd != null ? usd(kpi.revenue_per_1000_views_usd) : "—"}</div>
            <div className="af-kpi-label">Revenue / 1,000 views</div>
          </div>
          <div className="af-kpi">
            <div className="af-kpi-value">{usd(kpi.revenue_per_video_usd)}</div>
            <div className="af-kpi-label">Revenue / video ({kpi.videos_with_commercial_activity} video)</div>
          </div>
        </div>
      )}

      <section className="af-section">
        <h2 className="af-section-title">Đề xuất sản phẩm cho một câu chuyện (tham khảo)</h2>
        <p className="af-hint">
          Nhập mô tả audience/chủ đề (vd: "Female self-worth") -- AI đề xuất product category liên quan, sau đó hệ
          thống xếp hạng sản phẩm ACTIVE theo category khớp x Product Score. Chỉ để tham khảo, không tự động gắn vào
          story/video nào.
        </p>
        <div className="af-match-form">
          <input
            className="af-input af-input-wide"
            placeholder='vd: "Female self-worth"'
            value={storyText}
            onChange={(e) => setStoryText(e.target.value)}
          />
          <button className="btn btn-primary" onClick={handleMatch} disabled={!storyText.trim() || matching}>
            {matching ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />} Đề xuất
          </button>
        </div>
        {matchError && <div className="af-alert af-alert-error">{matchError}</div>}
        {matches && (
          matches.length === 0 ? (
            <p className="af-hint">Không có sản phẩm ACTIVE nào khớp category được đề xuất.</p>
          ) : (
            <div className="af-match-list">
              {matches.map((m) => (
                <div key={m.product.id} className="af-match-card">
                  <div className="af-match-top">
                    <strong>{m.product.name}</strong>
                    <span className="af-match-score">{m.final_score?.toFixed(1) ?? "—"}</span>
                  </div>
                  <ul className="af-match-reasons">
                    {m.reasons.map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )
        )}
      </section>

      <section className="af-section">
        <h2 className="af-section-title">Thêm sản phẩm</h2>
        <div className="af-form-grid">
          <input className="af-input" placeholder="Tên sản phẩm *" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input className="af-input" placeholder="Category *" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
          <input className="af-input" placeholder="Platform * (vd: amazon, shopee)" value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })} />
          <input className="af-input" placeholder="Giá" type="number" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} />
          <input className="af-input" placeholder="Commission rate (0-1)" type="number" step="0.01" value={form.commission_rate} onChange={(e) => setForm({ ...form, commission_rate: e.target.value })} />
          <input className="af-input" placeholder="Rating (0-5, nếu có)" type="number" step="0.1" value={form.rating} onChange={(e) => setForm({ ...form, rating: e.target.value })} />
          <input className="af-input af-input-wide" placeholder="Tags, cách nhau bởi dấu phẩy" value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} />
          <input className="af-input af-input-wide" placeholder="Affiliate URL *" value={form.affiliate_url} onChange={(e) => setForm({ ...form, affiliate_url: e.target.value })} />
        </div>
        <button className="btn btn-primary" onClick={handleCreateProduct} disabled={creating}>
          {creating ? <Loader2 size={14} className="spin" /> : <Plus size={14} />} Thêm sản phẩm
        </button>
      </section>

      <section className="af-section">
        <h2 className="af-section-title">Catalog sản phẩm</h2>
        {loading ? (
          <div className="af-loading">
            <Loader2 size={18} className="spin" />
          </div>
        ) : products.length === 0 ? (
          <EmptyState icon={Sparkles} title="Chưa có sản phẩm nào" description="Thêm sản phẩm ở form phía trên." />
        ) : (
          <div className="af-product-list">
            {products.map((p) => (
              <div key={p.id} className="af-product-card">
                <div className="af-product-top" onClick={() => setExpandedId(expandedId === p.id ? null : p.id)}>
                  <div>
                    <strong>{p.name}</strong>
                    <span className="af-product-category">{p.category}</span>
                    {!p.active && <span className="af-inactive-badge">Inactive</span>}
                  </div>
                  <div className="af-product-meta">
                    <span>{p.price != null ? usd(p.price) : "—"}</span>
                    <span>{p.commission_rate != null ? `${(p.commission_rate * 100).toFixed(0)}%` : "—"}</span>
                    <span className="af-score">{p.product_score != null ? p.product_score.toFixed(1) : "—"}</span>
                  </div>
                  <div className="af-product-actions">
                    <button
                      className="btn btn-secondary"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRecompute(p.id);
                      }}
                      disabled={recomputingId === p.id}
                    >
                      <RefreshCw size={12} className={recomputingId === p.id ? "spin" : ""} /> Score
                    </button>
                    <button
                      className="btn btn-secondary"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteProduct(p.id);
                      }}
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
                {p.product_score_breakdown && (
                  <p className="af-hint">{p.product_score_breakdown.notes.join(" ")}</p>
                )}
                {expandedId === p.id && <ProductLinks product={p} />}
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
