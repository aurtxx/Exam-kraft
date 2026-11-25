import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export const homeForRole = (role: string) => role === 'STUDENT' ? '/student' : '/staff/exams';

export function RoleHome() {
  const { user, isLoading } = useAuth();
  if (isLoading) return <p role="status">Loading workspace…</p>;
  return <Navigate to={user ? homeForRole(user.role) : '/login'} replace />;
}

export default function ProtectedRoutes({ student = false }: { student?: boolean }) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) return <p role="status">Loading workspace…</p>;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  if ((user.role === 'STUDENT') !== student) {
    return <Navigate to={homeForRole(user.role)} replace />;
  }
  return <Outlet />;
}
