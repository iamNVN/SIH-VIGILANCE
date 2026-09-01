import { AnimatePresence, motion } from "framer-motion";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const NAV_ITEMS = [
  { to: "/", label: "Command Center", tag: "CC", roles: ["investigator", "administrator"] },
  { to: "/analytics", label: "Analytics", tag: "AN", roles: ["administrator"] },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-surface-page">
      <div className="h-[3px] shrink-0 bg-series-1" />
      <div className="flex flex-1 overflow-hidden">
        <aside className="flex w-60 shrink-0 flex-col border-r border-surface-border bg-surface-raised">
          <div className="flex items-center gap-2 border-b border-surface-border px-5 py-4">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-series-1 text-sm font-bold text-white">
              PT
            </div>
            <div>
              <p className="text-sm font-semibold uppercase leading-none tracking-wide text-ink-primary">PredicTrace</p>
              <p className="mt-1 text-[10px] uppercase tracking-wide text-ink-muted">Cash-out interdiction system</p>
            </div>
          </div>

          <nav className="flex-1 space-y-1 px-3 py-4">
            {NAV_ITEMS.filter((item) => item.roles.includes(user?.role)).map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition ${
                    isActive ? "bg-series-1/15 text-series-1" : "text-ink-secondary hover:bg-white/5 hover:text-ink-primary"
                  }`
                }
              >
                <span className="id-tag rounded-sm border border-current/30 px-1 text-[10px] font-semibold">{item.tag}</span>
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="px-3 pb-2">
            <div className="flex items-center gap-2 rounded-md border border-status-good/20 bg-status-good/10 px-2.5 py-1.5">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-status-good opacity-75" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-status-good" />
              </span>
              <span className="id-tag text-[10px] font-medium uppercase tracking-wide text-status-good">System online</span>
            </div>
          </div>

          <div className="border-t border-surface-border p-3">
            <div className="flex items-center gap-2 rounded-md px-2 py-2">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-white/10 text-xs font-semibold text-ink-secondary">
                {user?.initials}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium leading-none text-ink-primary">{user?.name}</p>
                <p className="truncate text-[11px] uppercase tracking-wide text-ink-muted">{user?.role} · {user?.unit}</p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="mt-1 w-full rounded-md px-3 py-1.5 text-left text-xs font-medium text-ink-muted hover:bg-white/5 hover:text-ink-primary"
            >
              Sign out
            </button>
          </div>
        </aside>

        <main className="flex-1 overflow-y-auto">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
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
