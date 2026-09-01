import { createContext, useContext, useEffect, useState } from "react";

/**
 * Demo-mode access control -- deliberately not real authentication.
 *
 * Per the Execution Blueprint's own honesty framework (Section 14/16), real
 * RBAC/DPDP-compliant auth is national-roadmap scope, not a department-demo
 * requirement. This is a client-side persona picker so the dashboard can
 * visibly demonstrate role-aware navigation without adding backend auth
 * surface (password storage, sessions, tokens) that would only add risk
 * before a live demo. Never present this as production security.
 */
export const PERSONAS = [
  {
    id: "investigator-1",
    name: "Insp. Ananya Iyer",
    role: "investigator",
    unit: "Bengaluru Cyber Cell",
    initials: "AI",
  },
  {
    id: "investigator-2",
    name: "Insp. Rahul Verma",
    role: "investigator",
    unit: "Chennai Cyber Cell",
    initials: "RV",
  },
  {
    id: "admin-1",
    name: "Priya Nair",
    role: "administrator",
    unit: "I4C TAU Analyst",
    initials: "PN",
  },
  {
    id: "admin-2",
    name: "Vikram Singh",
    role: "administrator",
    unit: "State Cyber Cell Admin",
    initials: "VS",
  },
];

const STORAGE_KEY = "predictrace.session";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });

  useEffect(() => {
    if (user) localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
    else localStorage.removeItem(STORAGE_KEY);
  }, [user]);

  const login = (personaId) => {
    const persona = PERSONAS.find((p) => p.id === personaId);
    if (persona) setUser(persona);
  };
  const logout = () => setUser(null);

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
