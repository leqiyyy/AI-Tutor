import { clearAuthSession, getAuthSession, saveAuthSession } from "@/lib/auth-storage";
import { http } from "@/lib/http";
import { shouldUseMockApi } from "@/lib/env";
import { mockLogin, mockRegister, mockSendVerificationCode } from "@/mocks/auth";
import type {
  LoginRequest,
  LoginResult,
  RegisterRequest,
  RegisterResult,
  SendVerificationCodeRequest,
  SendVerificationCodeResult,
  UserProfile,
} from "@/types/auth";

export const authService = {
  async login(payload: LoginRequest): Promise<LoginResult> {
    const result = shouldUseMockApi
      ? await mockLogin(payload)
      : await http<LoginResult>("/auth/login", {
          method: "POST",
          body: payload,
          auth: false,
        });

    saveAuthSession({
      accessToken: result.accessToken,
      refreshToken: result.refreshToken,
      expiresAt: result.expiresAt,
      user: {
        ...result.user,
        isDemo: result.user.isDemo ?? result.isDemo,
      },
      isDemo: result.isDemo ?? result.user.isDemo,
    });

    return result;
  },

  async sendVerificationCode(
    payload: SendVerificationCodeRequest,
  ): Promise<SendVerificationCodeResult> {
    return shouldUseMockApi
      ? mockSendVerificationCode(payload)
      : http<SendVerificationCodeResult>("/auth/send-verify-code", {
          method: "POST",
          body: payload,
          auth: false,
        });
  },

  async register(payload: RegisterRequest): Promise<RegisterResult> {
    return shouldUseMockApi
      ? mockRegister(payload)
      : http<RegisterResult>("/auth/register", {
          method: "POST",
          body: payload,
          auth: false,
        });
  },

  async getCurrentUser(): Promise<UserProfile | null> {
    if (shouldUseMockApi) {
      return getAuthSession()?.user || null;
    }

    return http<UserProfile>("/auth/me");
  },

  logout() {
    clearAuthSession();
  },
};
