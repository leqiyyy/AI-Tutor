import { clearAuthSession, getAuthSession, saveAuthSession } from "@/lib/auth-storage";
import { http } from "@/lib/http";
import { shouldUseMockApi } from "@/lib/env";
import { getDefaultRouteForRole } from "@/lib/role-routes";
import { mockLogin, mockRegister, mockResetPassword, mockSendVerificationCode } from "@/mocks/auth";
import type {
  AppRole,
  LoginRequest,
  LoginResult,
  RegisterRequest,
  RegisterResult,
  ResetPasswordRequest,
  ResetPasswordResult,
  SendVerificationCodeRequest,
  SendVerificationCodeResult,
  UserProfile,
} from "@/types/auth";

type BackendLoginResult = {
  access_token?: string;
  accessToken?: string;
  refresh_token?: string;
  refreshToken?: string;
  expires_at?: string;
  expiresAt?: string;
  role?: AppRole;
  user_id?: string;
  userId?: string;
  real_name?: string;
  realName?: string;
  name?: string;
  display_name?: string;
  displayName?: string;
  account?: string;
  email?: string;
  is_demo?: boolean;
  isDemo?: boolean;
  user?: Partial<UserProfile> & {
    real_name?: string;
    realName?: string;
    display_name?: string;
    is_demo?: boolean;
  };
};

type BackendUserProfile = Partial<UserProfile> & {
  real_name?: string;
  realName?: string;
  display_name?: string;
  displayName?: string;
  student_id?: string | null;
  teacher_id?: string | null;
  is_demo?: boolean;
  isDemo?: boolean;
};

function normalizeUserProfile(
  payload: BackendUserProfile | undefined,
  fallback?: Partial<UserProfile>,
): UserProfile {
  const role = (payload?.role || fallback?.role || "student") as AppRole;
  const id = String(payload?.id || fallback?.id || "");
  const realName =
    payload?.name ||
    payload?.displayName ||
    payload?.display_name ||
    payload?.realName ||
    payload?.real_name ||
    fallback?.name ||
    fallback?.displayName ||
    "";
  const account =
    payload?.account ||
    payload?.email ||
    payload?.student_id ||
    payload?.teacher_id ||
    fallback?.account ||
    fallback?.email ||
    "";
  const email = payload?.email || fallback?.email || "";

  return {
    id,
    role,
    name: realName || account || role,
    displayName: realName || account || role,
    account: String(account),
    email,
    isDemo: payload?.isDemo ?? payload?.is_demo ?? fallback?.isDemo,
  };
}

function normalizeLoginResult(
  payload: BackendLoginResult,
  request: LoginRequest,
): LoginResult {
  const role = (payload.user?.role || payload.role || request.role) as AppRole;
  const user = normalizeUserProfile(
    {
      ...payload.user,
      id: payload.user?.id || payload.user_id || payload.userId,
      role,
      real_name:
        payload.user?.real_name ||
        payload.user?.realName ||
        payload.real_name ||
        payload.realName,
      displayName:
        payload.user?.displayName ||
        payload.user?.display_name ||
        payload.displayName ||
        payload.display_name,
      account: payload.user?.account || payload.account || request.account,
      email: payload.user?.email || payload.email || request.account,
      isDemo: payload.user?.isDemo ?? payload.isDemo,
      is_demo: payload.user?.is_demo ?? payload.is_demo,
    },
    {
      role,
      account: request.account,
      email: request.account.includes("@") ? request.account : "",
    },
  );

  return {
    accessToken: payload.accessToken || payload.access_token || "",
    refreshToken: payload.refreshToken || payload.refresh_token,
    expiresAt: payload.expiresAt || payload.expires_at,
    redirectTo: getDefaultRouteForRole(role),
    user,
    isDemo: payload.isDemo ?? payload.is_demo ?? user.isDemo,
  };
}

function buildBackendRegisterPayload(payload: RegisterRequest) {
  return {
    ...payload,
    real_name: payload.realName,
    verify_code: payload.verifyCode,
    confirm_password: payload.password,
    confirmPassword: payload.password,
    ...(payload.role === "student"
      ? {
          student_id: payload.studentId,
          class_no: payload.classNo,
        }
      : {
          teacher_id: payload.teacherId,
          id_card_no: payload.idCardNo,
          cert_file: payload.certFile,
        }),
  };
}

export const authService = {
  async login(payload: LoginRequest): Promise<LoginResult> {
    const result = shouldUseMockApi
      ? await mockLogin(payload)
      : normalizeLoginResult(
          await http<BackendLoginResult>("/auth/login", {
            method: "POST",
            body: payload,
            auth: false,
          }),
          payload,
        );

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
    if (shouldUseMockApi) {
      return mockSendVerificationCode(payload);
    }

    await http<unknown>("/auth/send-verify-code", {
      method: "POST",
      body: {
        email: payload.target,
        purpose: payload.purpose || "register",
      },
      auth: false,
    });

    return {
      cooldownSeconds: 60,
      delivery: payload.channel,
      maskedTarget: payload.target,
    };
  },

  async register(payload: RegisterRequest): Promise<RegisterResult> {
    if (shouldUseMockApi) {
      return mockRegister(payload);
    }

    await http<unknown>("/auth/register", {
      method: "POST",
      body: buildBackendRegisterPayload(payload),
      auth: false,
    });

    return {
      status: "created",
      message:
        payload.role === "teacher"
          ? "教师账号注册成功，可直接登录"
          : "学生账号注册成功，可直接登录",
      nextAction: "login",
    };
  },

  async resetPassword(payload: ResetPasswordRequest): Promise<ResetPasswordResult> {
    if (shouldUseMockApi) {
      return mockResetPassword(payload);
    }

    await http<unknown>("/auth/reset-password", {
      method: "POST",
      body: {
        email: payload.email.trim(),
        verify_code: payload.verifyCode.trim(),
        password: payload.password,
        confirm_password: payload.confirmPassword,
        confirmPassword: payload.confirmPassword,
      },
      auth: false,
    });

    return {
      status: "updated",
      message: "密码重置成功",
    };
  },

  async getCurrentUser(): Promise<UserProfile | null> {
    if (shouldUseMockApi) {
      return getAuthSession()?.user || null;
    }

    return normalizeUserProfile(await http<BackendUserProfile>("/auth/me"));
  },

  logout() {
    clearAuthSession();
  },
};
