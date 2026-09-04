import { AnimatePresence, motion } from "framer-motion";
import {
  Bell,
  ChevronDown,
  FileText,
  Folder,
  Home,
  MapPin,
  Settings as SettingsIcon,
  Share2,
  Target,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

// Role actually gates two different things here: which PAGES show up at
// all (Reports is administrator-only -- model/evaluation oversight isn't an
// investigator task), and, on the pages both roles share, how much DATA
// they see (every investigator persona carries a `city` in AuthContext;
// every list/stat/feed endpoint enforces it server-side -- see api/client.js
// and the FastAPI routes it calls). Administrators have `city: null`, so
// they see every jurisdiction nationally.
const NAV_ITEMS = [
  { to: "/", label: "Command Center", icon: Home, roles: ["investigator", "administrator"] },
  { to: "/cases", label: "Cases", icon: Folder, roles: ["investigator", "administrator"] },
  { to: "/rings", label: "Network Graph", icon: Share2, roles: ["investigator", "administrator"] },
  { to: "/predictions", label: "Predictions", icon: Target, roles: ["investigator", "administrator"] },
  { to: "/alerts", label: "Alerts", icon: Bell, roles: ["investigator", "administrator"] },
  { to: "/maps", label: "Maps", icon: MapPin, roles: ["investigator", "administrator"] },
  { to: "/analytics", label: "Reports", icon: FileText, roles: ["administrator"] },
  { to: "/settings", label: "Settings", icon: SettingsIcon, roles: ["investigator", "administrator"] },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-surface-page">
      <div className="h-[3px] shrink-0 bg-gradient-to-r from-series-1 via-status-good to-series-1" />
      <div className="flex flex-1 overflow-hidden">
        <aside className="flex w-64 shrink-0 flex-col border-r border-surface-border bg-surface-raised">
          <div className="flex items-center gap-3 border-b border-surface-border px-5 py-5">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-series-1 text-lg font-bold text-white">
              P
            </div>
            <div>
              <p className="text-sm font-semibold leading-none text-ink-primary">PredicTrace</p>
              <p className="mt-1 text-[11px] leading-tight text-ink-muted">Cash-out Intelligence<br />System</p>
            </div>
          </div>

          <nav className="flex-1 space-y-1 px-3 py-4">
            {NAV_ITEMS.filter((item) => item.roles.includes(user?.role)).map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition ${
                      isActive ? "bg-series-1 text-white" : "text-ink-secondary hover:bg-white/5 hover:text-ink-primary"
                    }`
                  }
                >
                  <Icon className="h-4 w-4 shrink-0" strokeWidth={2} />
                  {item.label}
                </NavLink>
              );
            })}
          </nav>

          <div className="px-3 pb-3">
            <div className="rounded-md border border-status-good/25 bg-status-good/10 px-3 py-2.5">
              <div className="flex items-center gap-2">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-status-good opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-status-good" />
                </span>
                <span className="text-xs font-semibold text-status-good">System Online</span>
              </div>
              <p className="mt-0.5 pl-4 text-[11px] text-ink-muted">All systems operational</p>
            </div>
          </div>

          <div className="relative border-t border-surface-border p-3">
            {menuOpen && (
              <button
                onClick={handleLogout}
                className="absolute inset-x-3 bottom-full mb-1 rounded-md border border-surface-border bg-surface-card px-3 py-2 text-left text-xs font-medium text-status-critical shadow-lg hover:bg-white/5"
              >
                Sign out
              </button>
            )}
            <button
              onClick={() => setMenuOpen((v) => !v)}
              className="flex w-full items-center gap-2.5 rounded-md px-2 py-2 text-left transition hover:bg-white/5"
            >
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-series-1/20 text-xs font-semibold text-series-1">
                {user?.initials}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium leading-none text-ink-primary">{user?.name}</p>
                <p className="truncate text-[11px] capitalize text-ink-muted">{user?.role}</p>
              </div>
              <ChevronDown className={`h-4 w-4 shrink-0 text-ink-muted transition-transform ${menuOpen ? "rotate-180" : ""}`} strokeWidth={2} />
            </button>
          </div>
        </aside>

        <main className="flex-1 overflow-y-auto">
          <AnimatePresence mode="wait">
            {/* Keyed on the CASE page, not the exact pathname -- a case
                workspace's 4 tabs (overview/graph/map/brief) are separate
                routes under the same /cases/:id, so keying on the full
                pathname made every tab click remount this entire branch:
                CaseWorkspace's own useApi calls for the complaint/prediction
                refired (refetching data that hadn't changed) and its
                persistent header/right-column re-animated in from scratch,
                even though only the tab's own inner content should have
                changed. Stripping the tab segment means all 4 tabs share
                one key (no remount on tab switch) while still remounting
                for a genuinely different page or a different case id. */}
            <motion.div
              key={location.pathname.replace(/\/(overview|graph|map|brief)$/, "")}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18 }}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
