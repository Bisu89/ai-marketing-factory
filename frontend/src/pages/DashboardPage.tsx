import { Film, HardDrive, Clock3, Layers } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import "./DashboardPage.css";

const STATS = [
  { label: "Tổng video", value: "0", icon: Film },
  { label: "Dung lượng đã dùng", value: "0 MB", icon: HardDrive },
  { label: "Đang tải", value: "0", icon: Clock3 },
  { label: "Collection", value: "0", icon: Layers },
];

export function DashboardPage() {
  return (
    <>
      <PageHeader title="Dashboard" subtitle="Tổng quan thư viện video của bạn" />
      <div className="stat-grid">
        {STATS.map(({ label, value, icon: Icon }) => (
          <div className="stat-card" key={label}>
            <div className="stat-card-icon">
              <Icon size={18} />
            </div>
            <div>
              <div className="stat-card-value">{value}</div>
              <div className="stat-card-label">{label}</div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
