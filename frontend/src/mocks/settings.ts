import { appEnv } from "@/lib/env";
import type {
  DeviceSession,
  PasswordChangePayload,
  PasswordChangeResult,
  StudentSettingsData,
  TeacherSettingsData,
  UploadAvatarPayload,
  UploadAvatarResult,
} from "@/types/settings";

// 用途: StudentSettings.tsx / TeacherSettings.tsx 初始化与联调阶段读写占位
// 页面来源: 学生个人设置、教师个人设置
// 未来接口归属: settingsService.get*/update*/changePassword/uploadAvatar/getDevices

async function waitForMockLatency() {
  await new Promise((resolve) => setTimeout(resolve, appEnv.mockLatencyMs));
}

export const mockStudentSettings: StudentSettingsData = {
  profile: {
    name: "李明",
    nameEn: "Li Ming",
    gender: "male",
    birthday: "2002-08-15",
    bio: "计算机科学与技术专业大三学生，热爱编程和算法，对分布式系统和人工智能方向充满兴趣。",
    email: "liming@student.whu.edu.cn",
    phone: "13912345678",
    wechat: "liming2002",
    qq: "987654321",
    hometown: "湖北省武汉市",
  },
  academic: {
    studentId: "2021301234",
    school: "武汉大学",
    college: "计算机学院",
    major: "计算机科学与技术",
    grade: "2021",
    classNumber: "计科01班",
    enrollYear: "2021",
    expectedGradYear: "2025",
    degree: "工学学士",
    studentType: "undergraduate",
    dormitory: "桂园3舍 306室",
    advisor: "王建国教授",
    gpa: "3.82",
    credits: "127",
  },
  notifications: {
    siteNotify: true,
    emailNotify: true,
    wechatNotify: false,
    deadlineRemind: true,
    teacherReply: true,
    aiSuggestion: true,
    examRemind: true,
    scoreRelease: true,
  },
  learning: {
    preferStyle: "visual",
    dailyGoal: "2",
    showLeaderboard: true,
    weeklyReport: true,
    aiAutoSuggest: true,
  },
  privacy: {
    showGrade: false,
    showLeaderboard: true,
    showBio: true,
    showContact: false,
    allowAIAnalyze: true,
  },
  interests: ["算法竞赛", "人工智能", "开源项目", "系统编程"],
};

export const mockTeacherSettings: TeacherSettingsData = {
  profile: {
    name: "王建国",
    nameEn: "Wang Jianguo",
    gender: "male",
    birthday: "1978-05-12",
    bio: "主要从事计算机网络、分布式系统和云计算方向的教学与科研工作。曾主持国家自然科学基金项目2项，发表SCI论文30余篇，获省级教学成果奖一等奖。",
    email: "wangjianguo@whu.edu.cn",
    phone: "13800138000",
    wechat: "wangjianguo_whu",
    website: "https://cs.whu.edu.cn/wangjianguo",
    school: "武汉大学",
    college: "计算机学院",
    department: "计算机科学与技术系",
    title: "教授",
    employeeId: "WHU-CS-20050312",
    teacherType: "full",
    researchArea: "计算机网络、分布式系统、云计算、边缘计算",
    officeLocation: "计算机学院大楼 A栋 512室",
    officeHours: "周二、周四 14:00-16:00",
    education: "博士",
    graduateSchool: "清华大学",
    degree: "工学博士",
    graduateYear: "2005",
    joinYear: "2005",
    teachingYears: "21",
  },
  notifications: {
    siteNotify: true,
    emailNotify: true,
    wechatNotify: false,
    studentQuestion: true,
    aiDislike: true,
    deadlineRemind: true,
    systemUpdate: false,
  },
  ai: {
    defaultStyle: "academic",
    autoReply: true,
    knowledgeBase: true,
    responseLanguage: "zh",
    maxTokens: "2000",
  },
  achievements: [
    {
      id: 1,
      type: "paper",
      title: "Edge Computing Resource Allocation in 5G Networks",
      year: "2023",
      journal: "IEEE Transactions on Network Science",
    },
    {
      id: 2,
      type: "award",
      title: "湖北省高等学校教学成果奖一等奖",
      year: "2022",
      journal: "湖北省教育厅",
    },
    {
      id: 3,
      type: "project",
      title: "国家自然科学基金面上项目：边缘计算任务卸载优化研究",
      year: "2021",
      journal: "国家自然科学基金委",
    },
  ],
};

export const mockDeviceSessions: DeviceSession[] = [
  {
    id: "device-current",
    deviceName: "Chrome on Windows",
    location: "武汉",
    lastActiveAt: "刚刚",
    current: true,
  },
  {
    id: "device-mobile",
    deviceName: "Safari on iPhone",
    location: "深圳",
    lastActiveAt: "2小时前",
    current: false,
  },
];

export async function getMockStudentSettings() {
  await waitForMockLatency();
  return structuredClone(mockStudentSettings);
}

export async function getMockTeacherSettings() {
  await waitForMockLatency();
  return structuredClone(mockTeacherSettings);
}

export async function mockUpdateStudentSettings(payload: StudentSettingsData) {
  await waitForMockLatency();
  return structuredClone(payload);
}

export async function mockUpdateTeacherSettings(payload: TeacherSettingsData) {
  await waitForMockLatency();
  return structuredClone(payload);
}

export async function mockChangePassword(
  payload: PasswordChangePayload,
): Promise<PasswordChangeResult> {
  await waitForMockLatency();

  if (!payload.oldPassword || !payload.newPassword || !payload.confirmPassword) {
    throw new Error("请填写完整的密码信息");
  }

  if (payload.newPassword !== payload.confirmPassword) {
    throw new Error("两次输入的新密码不一致");
  }

  return {
    status: "updated",
    message: "密码修改成功",
  };
}

export async function mockUploadAvatar(
  payload: UploadAvatarPayload,
): Promise<UploadAvatarResult> {
  await waitForMockLatency();

  return {
    url: `https://dummyimage.com/200x200/e2dbff/6b5ad6&text=${encodeURIComponent(
      payload.fileName.slice(0, 2) || "头像",
    )}`,
  };
}

export async function getMockDeviceSessions() {
  await waitForMockLatency();
  return structuredClone(mockDeviceSessions);
}
