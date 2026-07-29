import { History } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";

export function HistoryPage() {
  return (
    <>
      <PageHeader title="History" subtitle="Lịch sử các lượt tải, bao gồm cả lượt lỗi" />
      <EmptyState
        icon={History}
        title="Chưa có lịch sử"
        description="Các lượt tải (thành công hoặc lỗi) sẽ được ghi lại tại đây."
      />
    </>
  );
}
