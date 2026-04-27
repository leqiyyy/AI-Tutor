import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/hooks/use-auth";
import { getDefaultRouteForRole } from "@/lib/role-routes";
import type { AppRole } from "@/types/auth";

function AuthScreen({ message }: { message: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-6 text-sm text-gray-500">
      {message}
    </div>
  );
}

export function RequireAuth({ allowedRoles }: { allowedRoles?: AppRole[] }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <AuthScreen message="正在恢复登录状态..." />;
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to={getDefaultRouteForRole(user.role)} replace />;
  }

  return <Outlet />;
}

export function PublicOnlyRoute() {
  const { user, loading } = useAuth();

  if (loading) {
    return <AuthScreen message="正在检查登录状态..." />;
  }

  if (user) {
    return <Navigate to={getDefaultRouteForRole(user.role)} replace />;
  }

  return <Outlet />;
}
