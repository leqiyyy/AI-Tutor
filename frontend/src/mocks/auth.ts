import { appEnv } from "@/lib/env";
import { getDefaultRouteForRole } from "@/lib/role-routes";
import type {
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

async function waitForMockLatency() {
  await new Promise((resolve) => setTimeout(resolve, appEnv.mockLatencyMs));
}

function buildMockUser(role: LoginRequest["role"], account: string): UserProfile {
  const normalizedAccount = account.trim();
  const isDemo = normalizedAccount.toLowerCase().startsWith("demo");
  const displayNameMap = {
    student: "演示学生",
    teacher: "演示教师",
    admin: "演示管理员",
  } as const;

  return {
    id: `${role}-${normalizedAccount || "demo"}`,
    role,
    name: displayNameMap[role],
    displayName: displayNameMap[role],
    account: normalizedAccount,
    email: normalizedAccount.includes("@")
      ? normalizedAccount
      : `${normalizedAccount || role}@example.com`,
    isDemo,
  };
}

export async function mockLogin(request: LoginRequest): Promise<LoginResult> {
  await waitForMockLatency();

  if (!request.account.trim() || !request.password.trim()) {
    throw new Error("账号和密码不能为空");
  }

  return {
    accessToken: `mock-access-token-${request.role}-${Date.now()}`,
    refreshToken: `mock-refresh-token-${request.role}-${Date.now()}`,
    expiresAt: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
    redirectTo: getDefaultRouteForRole(request.role),
    user: buildMockUser(request.role, request.account),
    isDemo: request.account.trim().toLowerCase().startsWith("demo"),
  };
}

export async function mockSendVerificationCode(
  request: SendVerificationCodeRequest,
): Promise<SendVerificationCodeResult> {
  await waitForMockLatency();

  if (!request.target.trim()) {
    throw new Error(
      request.channel === "phone" ? "手机号不能为空" : "邮箱不能为空",
    );
  }

  return {
    cooldownSeconds: 60,
    delivery: request.channel,
    maskedTarget: request.target,
    previewCode: "123456",
  };
}

export async function mockResetPassword(
  request: ResetPasswordRequest,
): Promise<ResetPasswordResult> {
  await waitForMockLatency();

  if (!request.email.trim() || !request.verifyCode.trim()) {
    throw new Error("请填写邮箱和验证码");
  }
  if (request.password.length < 8 || !/[a-zA-Z]/.test(request.password) || !/\d/.test(request.password)) {
    throw new Error("密码不少于8位，且需包含字母和数字");
  }
  if (request.password !== request.confirmPassword) {
    throw new Error("两次输入的新密码不一致");
  }

  return {
    status: "updated",
    message: "密码重置成功",
  };
}

export async function mockRegister(
  request: RegisterRequest,
): Promise<RegisterResult> {
  await waitForMockLatency();

  if (!request.verifyCode.trim()) {
    throw new Error("请输入验证码");
  }

  return {
    status: "created",
    message:
      request.role === "teacher"
        ? "教师账号注册成功，可直接登录"
        : "学生账号注册成功，可直接登录",
    nextAction: "login",
  };
}
