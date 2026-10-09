import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, Loader2 } from "lucide-react";
import type { DocProjectDetail, Review } from "../../api/documentary";
import "./documentary.css";

export interface TabProps {
  project: DocProjectDetail;
  /** Re-fetch the project (state, gates) after something that can change it. */
  reloadProject: () => void;
}

export function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : "Có lỗi xảy ra.";
}

/**
 * Load on mount and whenever `key` changes. Existing data stays on screen while it
 * refetches (stale-while-revalidate): `loading` is true only until the first result,
 * so a background refresh never unmounts the tab and loses open editors/scroll.
 */
export function useLoader<T>(fn: () => Promise<T>, key: unknown) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const seq = useRef(0);
  const hasData = useRef(false);

  const reload = useCallback(() => {
    const mine = ++seq.current;
    return fnRef.current()
      .then((d) => {
        if (mine === seq.current) {
          hasData.current = true;
          setData(d);
          setError(null);
        }
      })
      .catch((e) => mine === seq.current && setError(errMsg(e)))
      .finally(() => mine === seq.current && setLoading(false));
  }, []);

  useEffect(() => {
    if (!hasData.current) setLoading(true);
    void reload();
  }, [key, reload]);

  return { data, error, loading, reload };
}

/** Runs one async action at a time, tracking busy + error for the UI. */
export function useAction() {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  async function run<T>(name: string, fn: () => Promise<T>, okMessage?: (r: T) => string): Promise<T | undefined> {
    setBusy(name);
    setError(null);
    setInfo(null);
    try {
      const r = await fn();
      if (okMessage) setInfo(okMessage(r));
      return r;
    } catch (e) {
      setError(errMsg(e));
      return undefined;
    } finally {
      setBusy(null);
    }
  }
  return { busy, error, info, run, notify: setInfo, clear: () => (setError(null), setInfo(null)) };
}

export function Notice({ kind, children }: { kind: "error" | "info" | "ok" | "warn"; children: ReactNode }) {
  const Icon = kind === "ok" ? CheckCircle2 : kind === "info" ? Info : AlertTriangle;
  return (
    <div className={`doc-notice doc-notice-${kind}`} role={kind === "error" ? "alert" : "status"}>
      <Icon size={16} />
      <div>{children}</div>
    </div>
  );
}

export function ActionFeedback({ error, info }: { error: string | null; info: string | null }) {
  return (
    <>
      {error && <Notice kind="error">{error}</Notice>}
      {info && <Notice kind="ok">{info}</Notice>}
    </>
  );
}

export function Busy({ label }: { label?: string }) {
  return (
    <span className="doc-busy">
      <Loader2 size={14} className="spin" /> {label ?? "Đang xử lý…"}
    </span>
  );
}

export function Loading() {
  return (
    <div className="doc-loading">
      <Loader2 size={18} className="spin" /> Đang tải…
    </div>
  );
}

export function Badge({ tone, children }: { tone: "ok" | "warn" | "bad" | "muted" | "info"; children: ReactNode }) {
  return <span className={`doc-badge doc-badge-${tone}`}>{children}</span>;
}

export function ReviewBox({ review, title }: { review: Review | null; title: string }) {
  if (!review) return null;
  return (
    <div className="doc-review">
      <div className="doc-review-title">
        {title} {review.ok ? <Badge tone="ok">Đạt</Badge> : <Badge tone="bad">{review.issues.length} vấn đề chặn</Badge>}
      </div>
      {review.issues.length > 0 && (
        <ul className="doc-issues">
          {review.issues.map((i, k) => (
            <li key={k} className="doc-issue-bad">
              {i.message}
            </li>
          ))}
        </ul>
      )}
      {review.warnings.length > 0 && (
        <ul className="doc-issues">
          {review.warnings.map((i, k) => (
            <li key={k} className="doc-issue-warn">
              {i.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="doc-field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
