export type AiRole = "student" | "teacher";
export type AiMessageRole = "user" | "ai";
export type AiFeedback = "like" | "dislike";
export type AiKnowledgeBase = "course" | "personal" | "global";
export type AiResponseStyle = "academic" | "inspire" | "debug";
export type AiAnswerMode = "auto" | "strict_course" | "quick_llm" | "teacher_tool";

export interface AiRouteMeta {
  route?: string;
  intent?: string;
  needsRetrieval?: boolean;
  retrievalUsed?: boolean;
  confidence?: number;
  reason?: string;
  answerMode?: AiAnswerMode;
  sourcePolicy?: string;
  forcedByMode?: boolean;
  displayLabel?: string;
}

export interface AiMessageSource {
  name: string;
  page: number;
  type: string;
  score?: number;
  retrievalScore?: number;
  rerankScore?: number;
  relevanceScore?: number;
  confidence?: number;
  chunkId?: string;
  materialId?: string;
  citationIndex?: number;
  citationLabel?: string;
  citationPath?: string;
  snippet?: string;
  rawText?: string;
}

export interface AiProgressEvent {
  stage: string;
  status: "pending" | "running" | "done" | "error";
  label: string;
  elapsedMs?: number;
  elapsed_ms?: number;
  details?: Record<string, unknown>;
}

export interface AiAttachment {
  id: string;
  name: string;
  size: number;
  mimeType: string;
  fileType: "image" | "pdf" | "docx" | "md" | "code" | "other";
  preview?: string;
  rawFile?: File;
  storageKey?: string;
}

export interface AiMessage {
  id: number;
  role: AiMessageRole;
  content: string;
  time: string;
  attachments?: AiAttachment[];
  sources?: AiMessageSource[];
  confidence?: number;
  quality?: Record<string, unknown>;
  reviewContext?: Record<string, unknown>;
  routeMeta?: AiRouteMeta;
  needsReview?: boolean;
  feedback?: AiFeedback;
  isWelcome?: boolean;
}

export interface AiConversation {
  id: number;
  backendSessionId?: string;
  title: string;
  createdAt: string;
  lastMessage: string;
  messages: AiMessage[];
}

export interface AiResourceRecommendation {
  id: number;
  title: string;
  type: "pdf" | "video" | "ppt" | "exercise" | "report" | "template";
  chapter: string;
  relevance: number;
  reason: string;
  matchKeywords: string[];
}

export interface AiTeacherQuestion {
  id: string | number;
  student: string;
  avatar: string;
  question: string;
  aiAnswer: string;
  confidence: number;
  confidenceLevel: "high" | "medium" | "low";
  sources: Array<{ name: string; page: number }>;
  time: string;
  status: "pending" | "adopted" | "replied";
  teacherReply?: string;
}

export interface AiFeedbackItem {
  id: string;
  messageId?: string;
  classId?: string;
  studentId?: string;
  studentName: string;
  conversationTitle: string;
  questionContent: string;
  aiAnswer: string;
  teacherAnswer?: string;
  reason: string;
  timestamp: string;
  status: "pending" | "resolved";
  trigger?: "low_confidence" | "dislike" | "manual";
  syncStatus?: "pending" | "synced" | "failed";
  syncNote?: string;
  quality?: Record<string, unknown>;
  reviewContext?: Record<string, unknown>;
  courseId?: string;
}

export interface CreateConversationPayload {
  title?: string;
}

export interface SendMessagePayload {
  conversationId?: number;
  classId?: string;
  courseId?: string;
  content: string;
  attachments?: AiAttachment[];
  answerMode?: AiAnswerMode;
  onProgress?: (event: AiProgressEvent) => void;
}

export interface ConversationContextPayload {
  conversationId: number;
  knowledgeBase: AiKnowledgeBase;
}

export interface ConversationStylePayload {
  conversationId: number;
  style: AiResponseStyle;
}

export interface SubmitFeedbackPayload {
  conversationId: number;
  messageId: number;
  reason: string;
  questionContent?: string;
  aiAnswer: string;
}

export interface ReplyAiQuestionPayload {
  questionId: string | number;
  reply: string;
}

export interface GenerateTeacherToolPayload {
  prompt: string;
  classId?: string;
}
