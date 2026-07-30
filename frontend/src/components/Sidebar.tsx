import { LayoutDashboard, Download, Library, History, Settings, Film, Scissors, Clapperboard } from "lucide-react";
import { NavLink } from "react-router-dom";
import "./Sidebar.css";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/download", label: "Download", icon: Download },
  { to: "/library", label: "Library", icon: Library },
  { to: "/history", label: "History", icon: History },
  { to: "/scene-cutter", label: "Scene Cutter", icon: Scissors },
  { to: "/video-composer", label: "Video Composer", icon: Clapperboard },
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
