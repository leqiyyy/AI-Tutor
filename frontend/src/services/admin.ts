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

export interface AdminAuditEvent {
  id: string;
  event_type: string;
  status: string;
  actor_id?: string | null;
  actor_role?: string | null;
  actor_name?: string | null;
  target_type?: string | null;
  target_id?: string | null;
  course_id?: string | null;
  class_id?: string | null;
  material_id?: string | null;
  summary?: string | null;
  extra_data?: Record<string, unknown>;
  created_at: string;
}

export interface AdminAuditEventsResponse {
  items: AdminAuditEvent[];
  total: number;
  page: number;
  page_size: number;
}

export interface ListAuditEventsParams {
  event_type?: string;
  status?: string;
  actor_role?: string;
  class_id?: string;
  course_id?: string;
  target_type?: string;
  page?: number;
  page_size?: number;
}

export const adminService = {
  async listAuditEvents(
    params: ListAuditEventsParams = {},
  ): Promise<AdminAuditEventsResponse> {
    if (shouldUseMockApi) {
      return { items: [], total: 0, page: params.page || 1, page_size: params.page_size || 30 };
    }

    return http<AdminAuditEventsResponse>("/admin/audit-events", {
      query: { ...params },
    });
  },

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
      method: "PUT",
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
