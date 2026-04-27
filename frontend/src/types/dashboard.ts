export type DashboardRole = "student" | "teacher" | "admin";

export type DashboardTone =
  | "blue"
  | "green"
  | "purple"
  | "orange"
  | "teal"
  | "red"
  | "amber"
  | "pink";

export type DashboardNotificationType =
  | "deadline"
  | "reply"
  | "exam"
  | "ai"
  | "material"
  | "question"
  | "dislike"
  | "system";

export interface DashboardNotification {
  id: string;
  type: DashboardNotificationType;
  title: string;
  content: string;
  time: string;
  unread: boolean;
}

export interface StudentDashboardCourse {
  id: string;
  name: string;
  teacher: string;
  progress: number;
  unread: number;
  image: string;
}

export interface StudentProgressCourse {
  id: string;
  name: string;
  progress: number;
  chapter: string;
  unread: number;
  color: DashboardTone;
}

export interface StudentPendingItem {
  id: string;
  title: string;
  description: string;
  tone: DashboardTone;
  icon: string;
  actionLabel: string;
  targetUrl: string;
}

export interface DashboardTextCard {
  id: string;
  title: string;
  content: string;
  tone: DashboardTone;
  icon?: string;
  meta?: string;
}

export interface StudentDashboardData {
  greetingName: string;
  stats: {
    activeCourses: number;
    pendingTasks: number;
    completionRate: number;
  };
  pendingItems: StudentPendingItem[];
  progressCourses: StudentProgressCourse[];
  recommendations: DashboardTextCard[];
  activities: DashboardTextCard[];
  notifications: DashboardNotification[];
  courses: StudentDashboardCourse[];
}

export interface TeacherDashboardCourse {
  id: string;
  name: string;
  code: string;
  students: number;
  unread: number;
  color: DashboardTone;
  image: string;
}

export interface TeacherCalendarEvent {
  id: string;
  day: string;
  date: number;
  title: string;
  sub: string;
  tag: string;
  tagColor: DashboardTone;
  icon: string;
}

export interface TeacherDashboardData {
  greetingName: string;
  stats: {
    activeCourses: number;
    totalStudents: number;
    pendingReviews: number;
    aiAnswerRate: number;
    manualAnswerRate: number;
    satisfactionScore: number;
    todayTodo: number;
    pendingQuestions: number;
    dueSoon: number;
    courseSetupCompleted: number;
    courseSetupTotal: number;
    weeklyStudentTrend: number[];
  };
  calendarEvents: TeacherCalendarEvent[];
  aiWeeklyMetrics: DashboardTextCard[];
  hotQuestionTopics: Array<{
    id: string;
    topic: string;
    count: number;
  }>;
  todoItems: DashboardTextCard[];
  warningItems: DashboardTextCard[];
  notifications: DashboardNotification[];
  courses: TeacherDashboardCourse[];
}

export interface AdminDashboardStat {
  id: string;
  label: string;
  value: string;
  change: string;
  tone: DashboardTone;
  icon: string;
}

export interface AdminTodoReminder {
  id: string;
  title: string;
  count: number;
  content: string;
  actionLabel: string;
  tone: DashboardTone;
}

export interface AdminActivity {
  id: string;
  type: "user" | "course" | "announcement" | "backup";
  title: string;
  content: string;
  time: string;
  color: DashboardTone;
}

export interface AdminSystemStatus {
  id: string;
  label: string;
  status: string;
  detail: string;
  tone: DashboardTone;
  progress?: number;
}

export interface AdminUserReview {
  id: string;
  name: string;
  role: "teacher" | "student" | "admin";
  roleLabel: string;
  department: string;
  accountNo: string;
  appliedAt: string;
}

export interface AdminUserRow {
  id: string;
  name: string;
  role: "teacher" | "student" | "admin";
  roleLabel: string;
  department: string;
  registeredAt: string;
  status: "online" | "offline" | "disabled";
  statusLabel: string;
}

export interface AdminCourseRow {
  id: string;
  name: string;
  teacher: string;
  students: number;
  knowledgeBaseStatus: "normal" | "warning" | "error";
  knowledgeBaseStatusLabel: string;
  documentCount: number;
  lastActive: string;
}

export interface AdminAuditAnswer {
  id: string;
  question: string;
  answer: string;
  dislikeCount: number;
  course: string;
}

export interface AdminAuditReport {
  id: string;
  type: string;
  content: string;
  reporter: string;
  time: string;
}

export interface AdminDashboardData {
  greetingName: string;
  stats: AdminDashboardStat[];
  todoReminders: AdminTodoReminder[];
  activities: AdminActivity[];
  systemStatus: AdminSystemStatus[];
  userReviews: AdminUserReview[];
  users: AdminUserRow[];
  courses: AdminCourseRow[];
  auditAnswers: AdminAuditAnswer[];
  auditReports: AdminAuditReport[];
  sensitiveWords: string[];
}
