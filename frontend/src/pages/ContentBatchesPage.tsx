import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Layers } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { listContentBatches } from "../api/contentBatch";
import type { ContentBatch } from "../types/contentBatch";
import "./ContentBatchesPage.css";

const STATUS_LABEL: Record<ContentBatch["status"], string> = {
  DRAFT: "Nháp",
  PROCESSING: "Đang xử lý",
  COMPLETED: "Hoàn tất",
  PARTIAL_FAILURE: "Một phần lỗi",
  FAILED: "Lỗi",
  CANCELLED: "Đã huỷ",
};

function itemSummary(batch: ContentBatch): string {
  const total = batch.items.length;
  const approved = batch.items.filter((i) => i.status === "APPROVED").length;
  const failed = batch.items.filter((i) => i.status === "FAILED").length;
  return `${approved}/${total} đạt${failed > 0 ? `, ${failed} lỗi` : ""}`;
}

export function ContentBatchesPage() {
  const navigate = useNavigate();
  const [batches, setBatches] = useState<ContentBatch[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    listContentBatches()
      .then(setBatches)
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Không tải được danh sách batch."));
  }, []);

  return (
    <>
      <PageHeader
        title="Content Batches"
        subtitle="Sinh và chấm điểm truyện hàng loạt từ các ý tưởng đã chọn ở Content Studio."
      />

      {loadError && <div className="cbatch-alert cbatch-alert-error">{loadError}</div>}

      {batches.length === 0 ? (
        <EmptyState
          icon={Layers}
          title="Chưa có batch nào"
          description="Chọn ý tưởng ở Content Studio rồi bấm 'Tạo Story hàng loạt' để bắt đầu."
        />
      ) : (
        <div className="cbatch-table-wrap">
          <table className="cbatch-table">
            <thead>
              <tr>
                <th>Tên</th>
                <th>Style</th>
                <th>Ngưỡng điểm</th>
                <th>Trạng thái</th>
                <th>Kết quả</th>
              </tr>
            </thead>
            <tbody>
              {batches.map((batch) => (
                <tr key={batch.id} onClick={() => navigate(`/content-batches/${batch.id}`)} className="cbatch-row-clickable">
                  <td>{batch.name}</td>
                  <td>{batch.style}</td>
                  <td>{batch.score_threshold.toFixed(1)}/10</td>
                  <td>
                    <span className={`cbatch-status cbatch-status--${batch.status}`}>{STATUS_LABEL[batch.status]}</span>
                  </td>
                  <td>{itemSummary(batch)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
