import { shouldUseMockApi } from "@/lib/env";
import { http } from "@/lib/http";
import type { DashboardRole } from "@/types/dashboard";

export const notificationService = {
  async markAsRead(_role: DashboardRole, notificationId: string): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/notifications/${notificationId}/read`, {
      method: "POST",
    });
  },

  async markAllAsRead(_role: DashboardRole): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>("/notifications/read-all", {
      method: "POST",
    });
  },
};
