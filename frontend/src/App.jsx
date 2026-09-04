import { Navigate, Route, HashRouter as Router, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import Alerts from "./pages/Alerts";
import Analytics from "./pages/Analytics";
import Brief from "./pages/case/Brief";
import CashOutMapPage from "./pages/case/CashOutMapPage";
import FundFlowGraph from "./pages/case/FundFlowGraph";
import Overview from "./pages/case/Overview";
import CaseWorkspace from "./pages/CaseWorkspace";
import Cases from "./pages/Cases";
import CommandCenter from "./pages/CommandCenter";
import FraudRings from "./pages/FraudRings";
import Login from "./pages/Login";
import Maps from "./pages/Maps";
import Predictions from "./pages/Predictions";
import Settings from "./pages/Settings";

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
            <Route path="/cases" element={<Cases />} />
            <Route path="/rings" element={<FraudRings />} />
            <Route path="/predictions" element={<Predictions />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/maps" element={<Maps />} />
            <Route
              path="/analytics"
              element={
                <ProtectedRoute roles={["administrator"]}>
                  <Analytics />
                </ProtectedRoute>
              }
            />
            <Route path="/settings" element={<Settings />} />

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
