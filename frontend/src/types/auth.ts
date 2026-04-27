export type AppRole = "student" | "teacher" | "admin";

export type RegisterRole = Exclude<AppRole, "admin">;

export interface UserProfile {
  id: string;
  role: AppRole;
  name: string;
  displayName: string;
  account: string;
  email: string;
  isDemo?: boolean;
}

export interface AuthSession {
  accessToken: string;
  refreshToken?: string;
  expiresAt?: string;
  user: UserProfile;
  isDemo?: boolean;
}

export interface LoginRequest {
  role: AppRole;
  account: string;
  password: string;
}

export interface LoginResult extends AuthSession {
  redirectTo: string;
}

export type VerificationChannel = "email" | "phone";

export interface SendVerificationCodeRequest {
  role: RegisterRole;
  channel: VerificationChannel;
  target: string;
}

export interface SendVerificationCodeResult {
  cooldownSeconds: number;
  delivery: VerificationChannel;
  maskedTarget?: string;
  previewCode?: string;
}

export interface StudentRegistrationRequest {
  role: "student";
  realName: string;
  studentId: string;
  email: string;
  phone: string;
  school: string;
  college: string;
  major: string;
  grade: string;
  classNo: string;
  password: string;
  verifyCode: string;
}

export interface TeacherRegistrationRequest {
  role: "teacher";
  realName: string;
  teacherId: string;
  email: string;
  phone: string;
  school: string;
  college: string;
  department: string;
  title: string;
  idCardNo: string;
  certFile?: string;
  password: string;
  verifyCode: string;
}

export type RegisterRequest =
  | StudentRegistrationRequest
  | TeacherRegistrationRequest;

export interface RegisterResult {
  status: "created";
  message: string;
  nextAction?: string;
}
