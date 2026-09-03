import {
  LayoutDashboard,
  Download,
  DollarSign,
  Library,
  History,
  Radar,
  ShoppingBag,
  Settings,
  Film,
  Scissors,
  Clapperboard,
  Images,
  Layers,
  ListChecks,
  ListVideo,
  MonitorPlay,
  Newspaper,
  Sparkles,
  Youtube,
  Trophy,
  Wand2,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import "./Sidebar.css";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/download", label: "Download", icon: Download },
  { to: "/library", label: "Library", icon: Library },
  { to: "/history", label: "History", icon: History },
  { to: "/content-studio", label: "Content Studio", icon: Sparkles },
  { to: "/news", label: "Tin tức", icon: Newspaper },
  { to: "/content-batches", label: "Content Batches", icon: ListChecks },
  { to: "/winners", label: "Winner Detection", icon: Trophy },
  { to: "/ai-costs", label: "AI Cost Tracking", icon: DollarSign },
  { to: "/competitor-intelligence", label: "Competitor Analyzer", icon: Radar },
  { to: "/affiliate", label: "Affiliate Engine", icon: ShoppingBag },
  { to: "/scene-cutter", label: "Scene Cutter", icon: Scissors },
  { to: "/video-composer", label: "Video Composer", icon: Clapperboard },
  { to: "/video-factory", label: "Video Factory", icon: Wand2 },
  { to: "/videos", label: "Videos", icon: MonitorPlay },
  { to: "/publishing", label: "Publishing", icon: Youtube },
  { to: "/batches", label: "Batches", icon: Layers },
  { to: "/series", label: "Series", icon: ListVideo },
  { to: "/asset-library", label: "Asset Library", icon: Images },
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
