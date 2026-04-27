import { http } from "@/lib/http";
import { shouldUseMockApi } from "@/lib/env";
import {
  mockAdminDashboard,
  mockStudentDashboard,
  mockTeacherDashboard,
} from "@/mocks/dashboard";
import type {
  AdminDashboardData,
  StudentDashboardData,
  TeacherDashboardData,
} from "@/types/dashboard";

export const dashboardService = {
  async getStudentDashboard(): Promise<StudentDashboardData> {
    return shouldUseMockApi
      ? mockStudentDashboard
      : http<StudentDashboardData>("/student/dashboard");
  },

  async getTeacherDashboard(): Promise<TeacherDashboardData> {
    return shouldUseMockApi
      ? mockTeacherDashboard
      : http<TeacherDashboardData>("/teacher/dashboard");
  },

  async getAdminDashboard(): Promise<AdminDashboardData> {
    return shouldUseMockApi
      ? mockAdminDashboard
      : http<AdminDashboardData>("/admin/dashboard");
  },
};
