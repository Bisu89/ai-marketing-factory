import { Outlet } from "react-router-dom";
import { Sidebar } from "../components/Sidebar";
import "./AppShell.css";

export function AppShell() {
  return (
    <div className="app-shell">
      <Sidebar />
      <main className="app-content">
        <Outlet />
      </main>
    </div>
  );
}
