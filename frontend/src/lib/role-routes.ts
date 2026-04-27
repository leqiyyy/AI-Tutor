import type { AppRole } from "@/types/auth";

const ROLE_HOME_PATHS: Record<AppRole, string> = {
  student: "/student-dashboard",
  teacher: "/teacher-dashboard",
  admin: "/admin-dashboard",
};

export function getDefaultRouteForRole(role: AppRole) {
  return ROLE_HOME_PATHS[role];
}
