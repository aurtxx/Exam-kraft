import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export const homeForRole = (role: string) => role === 'STUDENT' ? '/student' : '/staff/exams';

const WorkspaceLoading: React.FC = () => (
  <div
    role="status"
    className="min-h-screen flex items-center justify-center bg-slate-100 p-6"
  >
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm px-8 py-6 flex flex-col items-center gap-3 text-center">
      <div className="w-10 h-10 border-4 border-primary-500 border-t-transparent rounded-full animate-spin" />
      <p className="text-sm font-semibold text-slate-700">Loading workspace…</p>
    </div>
  </div>
);

export function RoleHome() {
  const { user, isLoading } = useAuth();
  if (isLoading) return <WorkspaceLoading />;
  return <Navigate to={user ? homeForRole(user.role) : '/login'} replace />;
}

export default function ProtectedRoutes({ student = false }: { student?: boolean }) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) return <WorkspaceLoading />;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  if ((user.role === 'STUDENT') !== student) {
    return <Navigate to={homeForRole(user.role)} replace />;
  }
  return <Outlet />;
}
