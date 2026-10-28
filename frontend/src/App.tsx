import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { AppLayout } from "./components/AppLayout";
import { Spinner } from "./components/ui";
import { CompaniesPage, CompanyDetailPage } from "./pages/Companies";
import { ContactDetailPage, ContactsPage } from "./pages/Contacts";
import { DashboardPage } from "./pages/DashboardPage";
import { DealDetailPage, DealsPage } from "./pages/Deals";
import { LeadDetailPage, LeadsPage } from "./pages/Leads";
import { LoginPage } from "./pages/LoginPage";
import { TasksPage } from "./pages/Tasks";

function RequireAuth() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Spinner label="Signing you in" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <AppLayout />;
}

function NotFound() {
  return (
    <div className="py-20 text-center">
      <h1 className="text-2xl font-semibold text-slate-900">Page not found</h1>
      <p className="mt-2 text-slate-600">The page you're looking for doesn't exist.</p>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route index element={<DashboardPage />} />
        <Route path="leads" element={<LeadsPage />} />
        <Route path="leads/:id" element={<LeadDetailPage />} />
        <Route path="deals" element={<DealsPage />} />
        <Route path="deals/:id" element={<DealDetailPage />} />
        <Route path="contacts" element={<ContactsPage />} />
        <Route path="contacts/:id" element={<ContactDetailPage />} />
        <Route path="companies" element={<CompaniesPage />} />
        <Route path="companies/:id" element={<CompanyDetailPage />} />
        <Route path="tasks" element={<TasksPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
