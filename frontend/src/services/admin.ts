import { shouldUseMockApi } from "@/lib/env";
import { http } from "@/lib/http";

export type AdminReviewDecision = "approve" | "reject";
export type AdminUserStatus = "enabled" | "disabled";
export type AdminCourseStatus = "active" | "archived" | "suspended";
export type AdminContentReviewDecision =
  | "approve"
  | "reject"
  | "delete"
  | "markIncorrect";

export interface ReviewRegistrationPayload {
  userId: string;
  decision: AdminReviewDecision;
  reason?: string;
}

export interface UpdateUserStatusPayload {
  userId: string;
  status: AdminUserStatus;
  reason?: string;
}

export interface UpdateCourseStatusPayload {
  courseId: string;
  status: AdminCourseStatus;
  reason?: string;
}

export interface ReviewContentPayload {
  itemId: string;
  decision: AdminContentReviewDecision;
  reason?: string;
}

export interface UpdateSystemSettingsPayload {
  maintenanceMode?: boolean;
  examWeekLimit?: boolean;
  backupSchedule?: string;
  announcement?: {
    title: string;
    content: string;
    audience: string;
  };
}

export const adminService = {
  async reviewRegistration(payload: ReviewRegistrationPayload): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>("/admin/registrations/review", {
      method: "POST",
      body: payload,
    });
  },

  async updateUserStatus(payload: UpdateUserStatusPayload): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/admin/users/${payload.userId}/status`, {
      method: "PATCH",
      body: payload,
    });
  },

  async updateCourseStatus(payload: UpdateCourseStatusPayload): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/admin/courses/${payload.courseId}/status`, {
      method: "PATCH",
      body: payload,
    });
  },

  async reviewContent(payload: ReviewContentPayload): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>("/admin/content/review", {
      method: "POST",
      body: payload,
    });
  },

  async updateSystemSettings(
    payload: UpdateSystemSettingsPayload,
  ): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>("/admin/system-settings", {
      method: "PATCH",
      body: payload,
    });
  },
};
