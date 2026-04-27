export interface CourseSummary {
  id: string;
  name: string;
  teacher: string;
  code: string;
}

export interface StudentCourseBootstrapData {
  course: CourseSummary;
  defaultSection: string;
  enrolledAt: string;
  completionRate: number;
  unreadCount: number;
}

export interface TeacherCourseBootstrapData {
  course: CourseSummary;
  defaultSection: string;
  inviteCode: string;
  studentCount: number;
  materialCount: number;
  pendingQuestionCount: number;
}

export type CourseRole = "student" | "teacher";

export interface KnowledgeGraphNode {
  id: string;
  label: string;
  x: number;
  y: number;
  parent?: string | null;
  color: string;
  type?: string;
  description?: string;
  hidden?: boolean;
  expandable?: boolean;
}

export interface KnowledgeGraphEdge {
  id: string;
  source: string;
  target: string;
  relationType?: string;
  label?: string;
  color?: string;
  dashed?: boolean;
}

export interface KnowledgeGraphMeta {
  rootNodeId?: string | null;
  layout?: "preset" | "force";
}

export interface KnowledgeGraphData {
  nodes: KnowledgeGraphNode[];
  edges?: KnowledgeGraphEdge[];
  meta?: KnowledgeGraphMeta;
}

export type StudentCourseMaterialType = "pdf" | "ppt" | "video" | "code";

export interface StudentCourseMaterial {
  id: string;
  name: string;
  type: StudentCourseMaterialType;
  size: string;
  date: string;
  views: number;
}

export interface StudentCourseMaterialsData {
  files: StudentCourseMaterial[];
}

export type TeacherCourseFileType = "PDF" | "PPT" | "Video";
export type TeacherCourseFileCategory =
  | "lecture"
  | "video"
  | "lab"
  | "exercise";

export interface TeacherCourseFile {
  id: number;
  name: string;
  type: TeacherCourseFileType;
  size: string;
  status: string;
  date: string;
  category: TeacherCourseFileCategory;
  downloads: number;
}

export interface TeacherCourseMaterialsData {
  files: TeacherCourseFile[];
}

export interface TeacherCourseMaterialAnalysisPoint {
  title: string;
  difficulty: "基础" | "中等" | "较难";
}

export interface TeacherCourseMaterialAnalysisDetail {
  fileId: number;
  summary: string;
  keyPoints: string[];
  difficulties: TeacherCourseMaterialAnalysisPoint[];
  recommendedStudyDuration: string;
  generatedAt: string;
}

export interface TeacherCourseMaterialPreviewData {
  fileId: number;
  previewType: "document" | "slide" | "video" | "unavailable";
  previewUrl: string;
  note: string;
  pageCount?: number;
  durationText?: string;
}

export interface TeacherCourseMaterialDownloadData {
  fileId: number;
  fileName: string;
  downloadUrl: string;
}

export interface TeacherCourseTask {
  id: number;
  type: string;
  title: string;
  deadline: string;
  submitted: number;
  total: number;
  status: string;
  publishDate: string;
  attachments: string[];
  startTime?: string;
  duration?: number;
}

export interface TeacherCourseTasksData {
  tasks: TeacherCourseTask[];
}

export interface TeacherCourseTaskSubmission {
  id: number;
  studentName: string;
  studentId: string;
  groupName: string;
  status: "submitted" | "pending" | "graded";
  submittedAt: string;
  score?: number;
  durationMinutes?: number;
}

export interface TeacherCourseTaskDetail extends TeacherCourseTask {
  description: string;
  requirements: string[];
  participantCount: number;
  averageScore?: number;
  highestScore?: number;
  lowestScore?: number;
  submissions: TeacherCourseTaskSubmission[];
}

export interface TeacherCourseHomeStat {
  label: string;
  value: string;
  sub: string;
  icon: string;
  iconBg: string;
  iconColor: string;
  trend: "up" | "warn" | null;
}

export interface TeacherCourseHomeTask {
  type: string;
  title: string;
  status: string;
  statusColor: string;
  submitted: number;
  total: number;
  deadline: string;
}

export interface TeacherCourseHomeWarningStudent {
  name: string;
  id: string;
  reason: string;
  progress: number;
  attendance: number;
  avatar: string;
}

export interface TeacherCourseHomeActivity {
  type: string;
  avatar: string;
  name: string;
  action: string;
  detail: string;
  time: string;
  color: string;
}

export interface TeacherCourseHomeWeeklyStat {
  label: string;
  value: string;
  unit: string;
  icon: string;
  color: string;
  bg: string;
}

export interface TeacherCourseHomeGroup {
  name: string;
  members: number;
  avg: number;
  leader: string;
  color: string;
}

export interface TeacherCourseHomeData {
  inviteCode: string;
  stats: TeacherCourseHomeStat[];
  recentTasks: TeacherCourseHomeTask[];
  warningStudents: TeacherCourseHomeWarningStudent[];
  activities: TeacherCourseHomeActivity[];
  weeklyStats: TeacherCourseHomeWeeklyStat[];
  groupPerformance: TeacherCourseHomeGroup[];
}

export interface TeacherQuestionReply {
  author: string;
  content: string;
  time: string;
}

export interface TeacherCourseQuestion {
  id: number;
  student: string;
  question: string;
  confidence: string;
  time: string;
  status: string;
  replies: TeacherQuestionReply[];
}

export interface TeacherCourseQuestionsData {
  questions: TeacherCourseQuestion[];
}

export interface TeacherCourseStudent {
  id: number;
  name: string;
  studentId: string;
  group: number;
  progress: number;
  homework: number;
  attendance: number;
  status: string;
  warningReason?: string;
}

export interface TeacherCourseStudentsData {
  students: TeacherCourseStudent[];
}

export interface CourseDiscussionReply {
  author: string;
  content: string;
  time: string;
  isTeacher?: boolean;
  isStudent?: boolean;
}

export interface CourseDiscussion {
  id: number;
  student: string;
  title: string;
  content: string;
  replies: CourseDiscussionReply[];
  likes: number;
  time: string;
  pinned?: boolean;
  liked: boolean;
}

export interface CourseDiscussionsData {
  discussions: CourseDiscussion[];
}

export interface StudentQuestionReply {
  author: string;
  content: string;
  time: string;
  isTeacher?: boolean;
}

export interface StudentCourseQuestion {
  id: number;
  title: string;
  content: string;
  time: string;
  status: string;
  replies: StudentQuestionReply[];
}

export interface StudentCourseQuestionsData {
  questions: StudentCourseQuestion[];
}

export interface CourseFaq {
  id: number;
  title: string;
  date: string;
  views: number;
  content: string;
  attachments: string[];
}

export interface CourseFaqsData {
  faqs: CourseFaq[];
}

export interface StudentHomeworkQuestion {
  id: number;
  content: string;
  type: string;
  answer: string;
  correct?: boolean;
  comment?: string;
}

export interface StudentCourseTask {
  id: string;
  title: string;
  deadline: string;
  status: string;
  score: number | null;
  urgent: boolean;
  questions: StudentHomeworkQuestion[];
  startTime?: string;
  duration?: number;
  isExam?: boolean;
  teacherComment?: string;
}

export interface StudentCourseTasksData {
  tasks: StudentCourseTask[];
}

export interface StudentCourseHomeWelcome {
  studentName: string;
  weeklyStudyHours: string;
  weeklyGoalRemaining: string;
  courseProgress: number;
  streakDays: number;
  homeworkCompleted: string;
  learnedChapters: string;
  aiQuestions: string;
}

export interface StudentCourseHomeAction {
  icon: string;
  label: string;
  sub: string;
  color: string;
  iconColor: string;
  section: string;
}

export interface StudentCourseHomeNotice {
  title: string;
  content: string;
  time: string;
  important: boolean;
  tag: string;
}

export interface StudentCourseHomeTask {
  title: string;
  deadline: string;
  urgent: boolean;
  icon: string;
}

export interface StudentCourseHomeUpdate {
  type: string;
  title: string;
  time: string;
  color: string;
  icon: string;
}

export interface StudentCourseHomeActivity {
  name: string;
  avatar: string;
  action: string;
  detail: string;
  time: string;
  avatarBg: string;
  icon: string;
  iconColor: string;
}

export interface StudentCourseHomeMilestone {
  title: string;
  date: string;
  done: boolean;
  current: boolean;
  urgent?: boolean;
}

export interface StudentCourseHomeProgress {
  percent: number;
  startDate: string;
  endDate: string;
}

export interface StudentCourseHomeData {
  welcome: StudentCourseHomeWelcome;
  quickActions: StudentCourseHomeAction[];
  notices: StudentCourseHomeNotice[];
  upcomingTasks: StudentCourseHomeTask[];
  todayUpdates: StudentCourseHomeUpdate[];
  classActivities: StudentCourseHomeActivity[];
  milestones: StudentCourseHomeMilestone[];
  progress: StudentCourseHomeProgress;
}

export interface JoinCourseRequest {
  inviteCode: string;
}

export interface JoinCourseResult {
  course: CourseSummary;
}

export interface CreateCourseRequest {
  name: string;
  code: string;
  semester: string;
  description?: string;
  coverColor?: string;
}

export interface CreateCourseResult {
  course: CourseSummary;
  inviteCode: string;
}

export interface GenerateInviteCodeResult {
  courseId: string;
  inviteCode: string;
  expiresAt?: string;
}
