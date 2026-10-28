import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import CalendarPage from "./pages/CalendarPage";
import DashboardPage from "./pages/DashboardPage";
import ExerciseLibraryPage from "./pages/ExerciseLibraryPage";
import LoginPage from "./pages/LoginPage";
import PatientEditPage from "./pages/PatientEditPage";
import PatientListPage from "./pages/PatientListPage";
import PatientRecordPage from "./pages/PatientRecordPage";
import SettingsPage from "./pages/SettingsPage";

export default function App() {
  const { status } = useAuth();
  if (!status) return <div className="splash">PhysioFlow wird geladen …</div>;
  if (!status.user) return <LoginPage setup={status.setup_required} />;

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="termine" element={<CalendarPage />} />
        <Route path="uebungen" element={<ExerciseLibraryPage />} />
        <Route path="patienten" element={<PatientListPage />} />
        <Route path="patienten/neu" element={<PatientEditPage />} />
        <Route path="patienten/:id/bearbeiten" element={<PatientEditPage />} />
        <Route path="patienten/:id/:tab?" element={<PatientRecordPage />} />
        <Route path="einstellungen" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
