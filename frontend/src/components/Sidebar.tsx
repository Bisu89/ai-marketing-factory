import {
  LayoutDashboard,
  Download,
  DollarSign,
  Library,
  History,
  BookOpen,
  Settings,
  Film,
  Clapperboard,
  Images,
  MonitorPlay,
  NotebookPen,
  Wand2,
  ImageDown,
  AudioLines,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import "./Sidebar.css";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/download", label: "Download", icon: Download },
  { to: "/storyteller", label: "Kể Truyện", icon: BookOpen },
  { to: "/library", label: "Library", icon: Library },
  { to: "/history", label: "History", icon: History },
  { to: "/studio", label: "Storytelling Studio", icon: NotebookPen },
  { to: "/ai-costs", label: "AI Cost Tracking", icon: DollarSign },
  { to: "/video-composer", label: "Video Composer", icon: Clapperboard },
  { to: "/video-factory", label: "Video Factory", icon: Wand2 },
  { to: "/videos", label: "Videos", icon: MonitorPlay },
  { to: "/asset-library", label: "Asset Library", icon: Images },
  { to: "/manhua-fetch", label: "Tải chương truyện", icon: ImageDown },
  { to: "/voice-test", label: "Thử giọng đọc", icon: AudioLines },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <Film size={20} />
        <span>AI Content Library</span>
      </div>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
          >
            <Icon size={18} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
