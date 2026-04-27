import { shouldUseMockApi } from "@/lib/env";
import { http } from "@/lib/http";
import type { DashboardRole } from "@/types/dashboard";

export const notificationService = {
  async markAsRead(role: DashboardRole, notificationId: string): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/${role}/notifications/${notificationId}/read`, {
      method: "POST",
    });
  },

  async markAllAsRead(role: DashboardRole): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/${role}/notifications/read-all`, {
      method: "POST",
    });
  },
};
