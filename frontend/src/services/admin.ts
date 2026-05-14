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

export interface AdminModelConfig {
  llm_provider?: string;
  llm_model?: string;
  llm_backend?: string;
  llm_local_api_base?: string;
  llm_temperature?: string | number;
  llm_top_p?: string | number;
  llm_enable_thinking?: boolean;
  llm_thinking_budget?: string | number;
  extract_model?: string;
  extract_temperature?: string | number;
  extract_top_p?: string | number;
  extract_enable_thinking?: boolean;
  extract_thinking_budget?: string | number;
  embedding_model?: string;
  embedding_backend?: string;
  embedding_local_api_base?: string;
  vlm_model?: string;
  vlm_backend?: string;
  vlm_local_api_base?: string;
  vlm_temperature?: string | number;
  vlm_top_p?: string | number;
  vlm_enable_thinking?: boolean;
  vlm_thinking_budget?: string | number;
  reranker_provider?: string;
  reranker_model?: string;
  reranker_local_model?: string;
  rag_engine?: string;
  storage_backend?: string;
  email_dev_mode?: boolean;
}

export interface AdminRagStorageConfig {
  rag_storage_backend?: string;
  vector_db_provider?: string;
  vector_db_url?: string;
  vector_db_collection?: string;
  graph_db_provider?: string;
  graph_db_url?: string;
  graph_db_database?: string;
  graph_db_username?: string;
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

  async getModelConfig(): Promise<AdminModelConfig> {
    return shouldUseMockApi ? {} : http<AdminModelConfig>("/admin/model-config");
  },

  async updateModelConfig(payload: AdminModelConfig): Promise<AdminModelConfig> {
    return shouldUseMockApi
      ? payload
      : http<AdminModelConfig>("/admin/model-config", {
          method: "PUT",
          body: payload,
        });
  },

  async getRagStorageConfig(): Promise<AdminRagStorageConfig> {
    return shouldUseMockApi ? {} : http<AdminRagStorageConfig>("/admin/rag-storage-config");
  },

  async updateRagStorageConfig(payload: AdminRagStorageConfig): Promise<AdminRagStorageConfig> {
    return shouldUseMockApi
      ? payload
      : http<AdminRagStorageConfig>("/admin/rag-storage-config", {
          method: "PUT",
          body: payload,
        });
  },
};
