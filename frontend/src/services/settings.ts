import { shouldUseMockApi } from "@/lib/env";
import { http } from "@/lib/http";
import {
  getMockDeviceSessions,
  getMockStudentSettings,
  getMockTeacherSettings,
  mockChangePassword,
  mockUpdateStudentSettings,
  mockUpdateTeacherSettings,
  mockUploadAvatar,
} from "@/mocks/settings";
import type {
  DeviceSession,
  PasswordChangePayload,
  PasswordChangeResult,
  StudentSettingsData,
  TeacherSettingsData,
  UploadAvatarPayload,
  UploadAvatarResult,
} from "@/types/settings";

export const settingsService = {
  async getStudentSettings(): Promise<StudentSettingsData> {
    return shouldUseMockApi
      ? getMockStudentSettings()
      : http<StudentSettingsData>("/student/settings");
  },

  async updateStudentSettings(
    payload: StudentSettingsData,
  ): Promise<StudentSettingsData> {
    return shouldUseMockApi
      ? mockUpdateStudentSettings(payload)
      : http<StudentSettingsData>("/student/settings", {
          method: "PUT",
          body: payload,
        });
  },

  async getTeacherSettings(): Promise<TeacherSettingsData> {
    return shouldUseMockApi
      ? getMockTeacherSettings()
      : http<TeacherSettingsData>("/teacher/settings");
  },

  async updateTeacherSettings(
    payload: TeacherSettingsData,
  ): Promise<TeacherSettingsData> {
    return shouldUseMockApi
      ? mockUpdateTeacherSettings(payload)
      : http<TeacherSettingsData>("/teacher/settings", {
          method: "PUT",
          body: payload,
        });
  },

  async changePassword(
    payload: PasswordChangePayload,
  ): Promise<PasswordChangeResult> {
    return shouldUseMockApi
      ? mockChangePassword(payload)
      : http<PasswordChangeResult>("/settings/password", {
          method: "POST",
          body: payload,
        });
  },

  async uploadAvatar(
    payload: UploadAvatarPayload,
  ): Promise<UploadAvatarResult> {
    return shouldUseMockApi
      ? mockUploadAvatar(payload)
      : http<UploadAvatarResult>("/settings/avatar", {
          method: "POST",
          body: payload,
        });
  },

  async getDevices(): Promise<DeviceSession[]> {
    return shouldUseMockApi
      ? getMockDeviceSessions()
      : http<DeviceSession[]>("/settings/devices");
  },
};
