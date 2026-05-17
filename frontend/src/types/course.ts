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
  canonicalName?: string | null;
  aliases?: string[];
  x: number;
  y: number;
  parent?: string | null;
  color: string;
  type?: string;
  description?: string;
  confidence?: number | null;
  sourceSpan?: Record<string, unknown>;
  provenance?: Record<string, unknown>;
  sourceSummary?: Record<string, unknown>;
  masteryScore?: number | null;
  masteryConfidence?: number | null;
  masteryEvidenceCount?: number;
  learningStatus?: "unknown" | "weak" | "needs_review" | "learning" | "mastered" | string;
  lastLearningEventAt?: string | null;
  hidden?: boolean;
  expandable?: boolean;
}

export interface KnowledgeGraphEdge {
  id: string;
  source: string;
  target: string;
  relationType?: string;
  label?: string;
  description?: string;
  summary?: string;
  color?: string;
  dashed?: boolean;
  confidence?: number | null;
  sourceSpan?: Record<string, unknown>;
  provenance?: Record<string, unknown>;
  sourceSummary?: Record<string, unknown>;
  weight?: number;
}

export interface KnowledgeGraphMeta {
  rootNodeId?: string | null;
  layout?: "preset" | "force";
}

export interface KnowledgeGraphEvidenceData {
  recordType: string;
  recordId: string;
  evidenceIndex: number;
  recordLabel?: string | null;
  material?: {
    id: string;
    title?: string | null;
    fileName?: string | null;
    fileType?: string | null;
    mimeType?: string | null;
    downloadUrl?: string | null;
    previewUrl?: string | null;
    viewUrl?: string | null;
  } | null;
  locator?: {
    page?: number | string | null;
    bbox?: unknown;
    modality?: string | null;
    contentIndex?: number | string | null;
    itemId?: string | null;
    atomicId?: string | null;
    chunkIds?: string[];
    coordinateSpace?: string | null;
  };
  content?: {
    textExcerpt?: string | null;
    formulaLatex?: string | null;
    tableMarkdown?: string | null;
    ocrText?: string | null;
  };
  asset?: {
    imagePathPreview?: string | null;
    sourcePathPreview?: string | null;
    imageUrl?: string | null;
    hasImagePath?: boolean;
    hasSourcePath?: boolean;
  };
  status?: {
    parseTaskStatus?: string | null;
    contentItemMatched?: boolean;
    viewerReady?: boolean;
  };
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
  status?: string;
  kbStatus?: string;
  kbError?: string | null;
}

export interface StudentCourseMaterialsData {
  files: StudentCourseMaterial[];
}

export interface CourseSearchResult {
  material_id: string;
  source_name?: string | null;
  source_type?: string | null;
  page?: number | null;
  chunk_id?: string | null;
  score: number;
  snippet: string;
}

export type TeacherCourseFileType = "PDF" | "PPT" | "Video";
export type TeacherCourseFileCategory =
  | "lecture"
  | "video"
  | "lab"
  | "exercise";

export interface TeacherCourseFile {
  id: string | number;
  name: string;
  type: TeacherCourseFileType;
  size: string;
  status: string;
  kbError?: string | null;
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
  fileId: string | number;
  summary: string;
  keyPoints: string[];
  difficulties: TeacherCourseMaterialAnalysisPoint[];
  recommendedStudyDuration: string;
  generatedAt: string;
}

export interface TeacherCourseMaterialPreviewData {
  fileId: string | number;
  previewType: "document" | "slide" | "video" | "unavailable";
  previewUrl: string;
  note: string;
  textContent?: string;
  textTruncated?: boolean;
  previewSource?: string;
  chunkCount?: number;
  downloadAvailable?: boolean;
  textPreviewAvailable?: boolean;
  retrievalAvailable?: boolean;
  pageCount?: number;
  durationText?: string;
}

export interface TeacherCourseMaterialDownloadData {
  fileId: string | number;
  fileName: string;
  downloadUrl: string;
}

export interface CourseTaskAttachment {
  id: string;
  fileName: string;
  size?: number | null;
  mimeType?: string | null;
  downloadUrl?: string;
}

export interface CourseTaskAttachmentsUploadData {
  attachments: CourseTaskAttachment[];
}

export interface TeacherCourseTask {
  id: string | number;
  type: string;
  title: string;
  deadline: string;
  submitted: number;
  total: number;
  status: string;
  publishDate: string;
  attachments: Array<string | CourseTaskAttachment>;
  startTime?: string;
  duration?: number;
  maxScore?: number;
  description?: string;
}

export interface TeacherCourseTasksData {
  tasks: TeacherCourseTask[];
}

export interface TaskQuestionGrade {
  questionId: string;
  content?: string;
  answer?: string;
  correctAnswer?: string;
  score: number;
  maxScore: number;
  correct: boolean;
  comment?: string;
  autoGraded?: boolean;
  requiresManualReview?: boolean;
}

export interface TeacherCourseTaskSubmission {
  id: string | number;
  studentName: string;
  studentId: string;
  groupName: string;
  status: "submitted" | "pending" | "graded";
  submittedAt: string;
  score?: number;
  durationMinutes?: number;
  feedback?: string;
  answers?: Record<string, string>;
  questionGrades?: TaskQuestionGrade[];
}

export interface TeacherCourseTaskDetail extends TeacherCourseTask {
  description: string;
  questions?: StudentHomeworkQuestion[];
  extraData?: Record<string, unknown>;
  requirements: string[];
  participantCount: number;
  averageScore?: number;
  highestScore?: number;
  lowestScore?: number;
  questionStats?: Array<{
    questionId: string | number;
    title: string;
    content: string;
    type: string;
    maxScore: number;
    submittedCount: number;
    gradedCount: number;
    correctCount: number;
    wrongCount: number;
    correctRate: number;
    averageScore: number;
  }>;
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
  averageScore?: number | null;
  submittedTasks?: number;
  totalTasks?: number;
  activityCount30d?: number;
}

export interface TeacherCourseStudentsData {
  students: TeacherCourseStudent[];
}

export interface TeacherStudentGroupMoveResult {
  movedCount: number;
  targetGroup: number | string;
  persisted?: boolean;
}

export interface TeacherStudentExportRow extends TeacherCourseStudent {
  email?: string;
}

export interface TeacherStudentExportData {
  format: string;
  fields: string[];
  students: TeacherStudentExportRow[];
  count: number;
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
  explanation?: string;
  correct?: boolean;
  comment?: string;
  correctAnswer?: string;
  score?: number;
  maxScore?: number;
}

export interface StudentCourseTask {
  id: string;
  title: string;
  deadline: string;
  status: string;
  score: number | null;
  urgent: boolean;
  questions: StudentHomeworkQuestion[];
  attachments?: Array<string | CourseTaskAttachment>;
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
