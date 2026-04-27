export interface StudentProfileSettings {
  name: string;
  nameEn: string;
  gender: string;
  birthday: string;
  bio: string;
  email: string;
  phone: string;
  wechat: string;
  qq: string;
  hometown: string;
}

export interface StudentAcademicSettings {
  studentId: string;
  school: string;
  college: string;
  major: string;
  grade: string;
  classNumber: string;
  enrollYear: string;
  expectedGradYear: string;
  degree: string;
  studentType: string;
  dormitory: string;
  advisor: string;
  gpa: string;
  credits: string;
}

export interface StudentNotificationSettings {
  siteNotify: boolean;
  emailNotify: boolean;
  wechatNotify: boolean;
  deadlineRemind: boolean;
  teacherReply: boolean;
  aiSuggestion: boolean;
  examRemind: boolean;
  scoreRelease: boolean;
}

export interface StudentLearningPreferences {
  preferStyle: string;
  dailyGoal: string;
  showLeaderboard: boolean;
  weeklyReport: boolean;
  aiAutoSuggest: boolean;
}

export interface StudentPrivacySettings {
  showGrade: boolean;
  showLeaderboard: boolean;
  showBio: boolean;
  showContact: boolean;
  allowAIAnalyze: boolean;
}

export interface StudentSettingsData {
  profile: StudentProfileSettings;
  academic: StudentAcademicSettings;
  notifications: StudentNotificationSettings;
  learning: StudentLearningPreferences;
  privacy: StudentPrivacySettings;
  interests: string[];
  avatarUrl?: string;
}

export interface TeacherProfileSettings {
  name: string;
  nameEn: string;
  gender: string;
  birthday: string;
  bio: string;
  email: string;
  phone: string;
  wechat: string;
  website: string;
  school: string;
  college: string;
  department: string;
  title: string;
  employeeId: string;
  teacherType: string;
  researchArea: string;
  officeLocation: string;
  officeHours: string;
  education: string;
  graduateSchool: string;
  degree: string;
  graduateYear: string;
  joinYear: string;
  teachingYears: string;
}

export interface TeacherNotificationSettings {
  siteNotify: boolean;
  emailNotify: boolean;
  wechatNotify: boolean;
  studentQuestion: boolean;
  aiDislike: boolean;
  deadlineRemind: boolean;
  systemUpdate: boolean;
}

export interface TeacherAiSettings {
  defaultStyle: string;
  autoReply: boolean;
  knowledgeBase: boolean;
  responseLanguage: string;
  maxTokens: string;
}

export interface TeacherAchievement {
  id: number;
  type: string;
  title: string;
  year: string;
  journal: string;
}

export interface TeacherSettingsData {
  profile: TeacherProfileSettings;
  notifications: TeacherNotificationSettings;
  ai: TeacherAiSettings;
  achievements: TeacherAchievement[];
  avatarUrl?: string;
}

export interface PasswordChangePayload {
  oldPassword: string;
  newPassword: string;
  confirmPassword: string;
}

export interface PasswordChangeResult {
  status: "updated";
  message: string;
}

export interface UploadAvatarPayload {
  fileName: string;
}

export interface UploadAvatarResult {
  url: string;
}

export interface DeviceSession {
  id: string;
  deviceName: string;
  location: string;
  lastActiveAt: string;
  current: boolean;
}
