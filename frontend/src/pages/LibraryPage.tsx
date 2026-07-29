import { Library } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";

export function LibraryPage() {
  return (
    <>
      <PageHeader title="Library" subtitle="Toàn bộ video đã tải về, có thể tìm kiếm và lọc" />
      <EmptyState
        icon={Library}
        title="Thư viện đang trống"
        description="Video sau khi tải xong từ trang Download sẽ xuất hiện ở đây."
      />
    </>
  );
}
