import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function ProtectedRoute({ children, roles }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  // Role gate, not just a hidden nav link -- an investigator typing
  // /analytics directly gets redirected, not a page the sidebar merely
  // didn't link to.
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />;
  return children;
}
