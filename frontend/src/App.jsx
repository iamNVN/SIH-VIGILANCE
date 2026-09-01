import { Navigate, Route, HashRouter as Router, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import Analytics from "./pages/Analytics";
import Brief from "./pages/case/Brief";
import CashOutMapPage from "./pages/case/CashOutMapPage";
import FundFlowGraph from "./pages/case/FundFlowGraph";
import Overview from "./pages/case/Overview";
import CaseWorkspace from "./pages/CaseWorkspace";
import CommandCenter from "./pages/CommandCenter";
import Login from "./pages/Login";

export default function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<CommandCenter />} />
            <Route path="/analytics" element={<Analytics />} />

            <Route path="/cases/:id" element={<CaseWorkspace />}>
              <Route index element={<Navigate to="overview" replace />} />
              <Route path="overview" element={<Overview />} />
              <Route path="graph" element={<FundFlowGraph />} />
              <Route path="map" element={<CashOutMapPage />} />
              <Route path="brief" element={<Brief />} />
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}
