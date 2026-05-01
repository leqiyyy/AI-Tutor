import { shouldUseMockApi } from "@/lib/env";
import { getAuthSession } from "@/lib/auth-storage";
import { buildUrl, http, HttpError } from "@/lib/http";
import {
  getMockConversationMessages,
  getMockConversations,
  getMockFeedbackQueue,
  getMockMessageSources,
  getMockRecommendations,
  getMockTeacherAiQuestionDetail,
  getMockTeacherAiQuestions,
  mockAdoptAiAnswer,
  mockCreateConversation,
  mockDeleteConversation,
  mockDislikeMessage,
  mockEscalateToTeacher,
  mockGenerateExam,
  mockGenerateFlashcards,
  mockGenerateLearningAnalysis,
  mockGenerateLessonPlan,
  mockLikeMessage,
  mockReplyAiQuestion,
  mockResolveFeedback,
  mockSendMessage,
  mockSubmitFeedback,
  mockUpdateConversationContext,
  mockUpdateConversationStyle,
  mockUploadAttachment,
} from "@/mocks/ai";
import type {
  AiAttachment,
  AiConversation,
  AiFeedbackItem,
  AiMessage,
  AiProgressEvent,
  AiRouteMeta,
  AiMessageSource,
  AiResourceRecommendation,
  AiTeacherQuestion,
  ConversationContextPayload,
  ConversationStylePayload,
  CreateConversationPayload,
  GenerateTeacherToolPayload,
  ReplyAiQuestionPayload,
  SendMessagePayload,
  SubmitFeedbackPayload,
} from "@/types/ai";

type ConversationRole = "student" | "teacher";

function conversationBasePath(role: ConversationRole) {
  return role === "student" ? "/student/ai" : "/teacher/ai";
}

type BackendSession = {
  id: string;
  title?: string;
  created_at?: string;
  updated_at?: string;
  last_message?: string;
};

type BackendMessage = {
  id: string;
  role: "user" | "assistant" | "ai";
  content: string;
  created_at?: string;
  attachments?: BackendAttachment[];
  sources?: Array<{
    name?: string;
    file_name?: string;
    fileName?: string;
    page?: number;
    type?: string;
    source_type?: string;
    sourceType?: string;
    score?: number;
    retrieval_score?: number;
    retrievalScore?: number;
    rerank_score?: number;
    rerankScore?: number;
    relevance_score?: number;
    relevanceScore?: number;
    confidence?: number;
    citation_index?: number;
    citationIndex?: number;
    citation_label?: string;
    citationLabel?: string;
    citation_path?: string;
    citationPath?: string;
    chunk_id?: string;
    chunkId?: string;
    material_id?: string;
    materialId?: string;
    snippet?: string;
    raw_text?: string;
    rawText?: string;
  }>;
  confidence?: number;
  quality?: Record<string, unknown>;
  review_context?: Record<string, unknown>;
  needs_review?: boolean;
  feedback?: "like" | "dislike";
};

type BackendQueryResult = {
  session_id?: string;
  message_id?: string;
  content?: string;
  sources?: BackendMessage["sources"];
  confidence?: number;
  quality?: Record<string, unknown>;
  review_context?: Record<string, unknown>;
  route_meta?: BackendRouteMeta;
  answer_mode?: SendMessagePayload["answerMode"];
  resolved_route?: string;
  retrieval_used?: boolean;
  source_policy?: string;
  needs_review?: boolean;
};

type BackendRouteMeta = {
  route?: string;
  intent?: string;
  needs_retrieval?: boolean;
  needsRetrieval?: boolean;
  retrieval_used?: boolean;
  retrievalUsed?: boolean;
  confidence?: number;
  reason?: string;
  answer_mode?: SendMessagePayload["answerMode"];
  answerMode?: SendMessagePayload["answerMode"];
  source_policy?: string;
  sourcePolicy?: string;
  forced_by_mode?: boolean;
  forcedByMode?: boolean;
  display_label?: string;
  displayLabel?: string;
};

type BackendAttachment = {
  id?: string;
  name?: string;
  file_name?: string;
  fileName?: string;
  size?: number;
  mime_type?: string;
  mimeType?: string;
  file_type?: AiAttachment["fileType"];
  fileType?: AiAttachment["fileType"];
  storage_key?: string;
  storageKey?: string;
  preview?: string;
};

type BackendQueryRequest = {
  class_id?: string;
  course_id?: string;
  session_id?: string;
  message: string;
  answer_mode?: SendMessagePayload["answerMode"];
  attachments: Array<{
    id: string;
    name: string;
    size: number;
    mime_type: string;
    file_type: AiAttachment["fileType"];
    storage_key: string;
  }>;
};

type BackendReviewItem = {
  id: string;
  message_id?: string;
  class_id?: string;
  student_id?: string;
  student_name?: string;
  trigger?: "low_confidence" | "dislike" | "manual";
  question_content?: string;
  ai_answer?: string;
  teacher_answer?: string;
  feedback_reason?: string;
  status?: "pending" | "resolved" | "dismissed";
  quality?: Record<string, unknown>;
  review_context?: Record<string, unknown>;
  created_at?: string;
};

const sessionIdMap = new Map<number, string>();
const reverseSessionIdMap = new Map<string, number>();
const messageIdMap = new Map<number, string>();

function numericConversationId(backendId: string) {
  const existing = reverseSessionIdMap.get(backendId);
  if (existing) {
    return existing;
  }
  const next = Date.now() + reverseSessionIdMap.size;
  reverseSessionIdMap.set(backendId, next);
  sessionIdMap.set(next, backendId);
  return next;
}

function normalizeSource(source: NonNullable<BackendMessage["sources"]>[number]): AiMessageSource {
  return {
    name: source.name || source.file_name || source.fileName || "课程资料",
    page: Number(source.page || 0),
    type: source.type || source.source_type || source.sourceType || "document",
    score: source.score,
    retrievalScore: source.retrieval_score ?? source.retrievalScore,
    rerankScore: source.rerank_score ?? source.rerankScore,
    relevanceScore: source.relevance_score ?? source.relevanceScore,
    confidence: source.confidence,
    chunkId: source.chunk_id ?? source.chunkId,
    materialId: source.material_id ?? source.materialId,
    citationIndex: source.citation_index ?? source.citationIndex,
    citationLabel: source.citation_label ?? source.citationLabel,
    citationPath: source.citation_path ?? source.citationPath,
    snippet: source.snippet,
    rawText: source.raw_text ?? source.rawText,
  };
}

function normalizeAttachment(attachment: BackendAttachment): AiAttachment | undefined {
  const name = attachment.name || attachment.file_name || attachment.fileName || "attachment";
  const mimeType = attachment.mime_type || attachment.mimeType || "application/octet-stream";
  const fileType = attachment.file_type || attachment.fileType || guessFileType(name, mimeType);
  return {
    id: String(attachment.id || attachment.storage_key || attachment.storageKey || name),
    name,
    size: Number(attachment.size || 0),
    mimeType,
    fileType,
    storageKey: attachment.storage_key || attachment.storageKey,
    preview: attachment.preview,
  };
}

function guessFileType(name: string, mimeType: string): AiAttachment["fileType"] {
  const lowerName = name.toLowerCase();
  const lowerMime = mimeType.toLowerCase();
  if (lowerMime.startsWith("image/")) return "image";
  if (lowerMime === "application/pdf" || lowerName.endsWith(".pdf")) return "pdf";
  if (lowerName.endsWith(".docx") || lowerName.endsWith(".doc")) return "docx";
  if (lowerName.endsWith(".md") || lowerName.endsWith(".markdown")) return "md";
  if (/\.(py|js|ts|tsx|java|cpp|c|go|rs)$/.test(lowerName)) return "code";
  return "other";
}

function normalizeRouteMeta(meta?: BackendRouteMeta): AiRouteMeta | undefined {
  if (!meta) return undefined;
  return {
    route: meta.route,
    intent: meta.intent,
    needsRetrieval: meta.needs_retrieval ?? meta.needsRetrieval,
    retrievalUsed: meta.retrieval_used ?? meta.retrievalUsed,
    confidence: meta.confidence,
    reason: meta.reason,
    answerMode: meta.answer_mode ?? meta.answerMode,
    sourcePolicy: meta.source_policy ?? meta.sourcePolicy,
    forcedByMode: meta.forced_by_mode ?? meta.forcedByMode,
    displayLabel: meta.display_label ?? meta.displayLabel,
  };
}

function normalizeMessage(message: BackendMessage): AiMessage {
  const id = Math.abs(hashString(message.id));
  messageIdMap.set(id, message.id);
  return {
    id,
    role: message.role === "user" ? "user" : "ai",
    content: message.content,
    time: message.created_at || new Date().toISOString(),
    attachments: message.attachments?.map(normalizeAttachment).filter((item): item is AiAttachment => Boolean(item)),
    sources: message.sources?.map(normalizeSource),
    confidence: message.confidence,
    quality: message.quality,
    reviewContext: message.review_context,
    needsReview: message.needs_review,
    feedback: message.feedback,
  };
}

function normalizeFeedbackItem(item: BackendReviewItem): AiFeedbackItem {
  const reviewContext = item.review_context || {};
  const studentReason = String(item.feedback_reason || "").trim();
  return {
    id: item.id,
    messageId: item.message_id,
    classId: item.class_id,
    studentId: item.student_id,
    studentName: item.student_name || "学生",
    conversationTitle:
      item.trigger === "low_confidence"
        ? "低置信回答待审核"
        : item.trigger === "manual"
          ? "学生转交教师"
          : "学生点踩反馈",
    questionContent: item.question_content || "",
    aiAnswer: item.ai_answer || "",
    teacherAnswer: item.teacher_answer || "",
    reason: studentReason,
    timestamp: item.created_at || new Date().toISOString(),
    status: item.status === "resolved" ? "resolved" : "pending",
    trigger: item.trigger,
    quality: item.quality,
    reviewContext,
  };
}

function normalizeConversation(session: BackendSession, messages: AiMessage[] = []): AiConversation {
  const id = numericConversationId(session.id);
  return {
    id,
    backendSessionId: session.id,
    title: session.title || "新对话",
    createdAt: session.created_at || new Date().toISOString(),
    lastMessage: session.last_message || "",
    messages,
  };
}

function hashString(value: string) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(index);
    hash |= 0;
  }
  return hash || Date.now();
}

async function uploadLiveAttachments(
  attachments: AiAttachment[] | undefined,
  classId?: string,
): Promise<AiAttachment[]> {
  if (!attachments?.length) {
    return [];
  }

  const uploaded: AiAttachment[] = [];
  for (const attachment of attachments) {
    if (!attachment.rawFile) {
      uploaded.push(attachment);
      continue;
    }

    const formData = new FormData();
    formData.append("file", attachment.rawFile);
    if (classId) {
      formData.append("class_id", classId);
    }
    const result = await http<BackendAttachment>("/chat/attachments/upload", {
      method: "POST",
      body: formData,
    });

    uploaded.push({
      ...attachment,
      id: result.id || result.storage_key || attachment.id,
      storageKey: result.storage_key,
      rawFile: undefined,
    });
  }

  return uploaded;
}

function authHeaders() {
  const headers = new Headers({ "Content-Type": "application/json" });
  const session = getAuthSession();
  if (session?.accessToken) {
    headers.set("Authorization", `Bearer ${session.accessToken}`);
  }
  return headers;
}

async function parseErrorResponse(response: Response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    try {
      const payload = await response.json();
      if (payload && typeof payload === "object" && "message" in payload) {
        const message = (payload as { message?: unknown }).message;
        if (typeof message === "string" && message.trim()) {
          return { message, payload };
        }
      }
      return { message: response.statusText || "请求失败", payload };
    } catch {
      return { message: response.statusText || "请求失败" };
    }
  }
  return { message: (await response.text()) || response.statusText || "请求失败" };
}

async function streamChatQuery(
  body: BackendQueryRequest,
  onProgress: (event: AiProgressEvent) => void,
): Promise<BackendQueryResult> {
  let response: Response;
  try {
    response = await fetch(buildUrl("/chat/query/stream"), {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(body),
      credentials: "include",
    });
  } catch (error) {
    throw new HttpError("网络请求失败，请检查后端服务是否已启动", {
      status: 0,
      details: error,
    });
  }

  if (!response.ok) {
    const parsed = await parseErrorResponse(response);
    throw new HttpError(parsed.message, {
      status: response.status,
      details: parsed.payload,
    });
  }
  if (!response.body) {
    throw new HttpError("浏览器未能建立流式连接", { status: response.status });
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResult: BackendQueryResult | undefined;
  let streamError: string | undefined;

  const consumeBlock = (block: string) => {
    let eventName = "message";
    const dataLines: string[] = [];
    for (const rawLine of block.split(/\r?\n/)) {
      const line = rawLine.trimEnd();
      if (!line || line.startsWith(":")) continue;
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trimStart());
      }
    }
    if (!dataLines.length) return;
    const dataText = dataLines.join("\n");
    const data = JSON.parse(dataText) as Record<string, unknown>;
    if (eventName === "progress") {
      onProgress(data as unknown as AiProgressEvent);
    } else if (eventName === "final") {
      finalResult = data as BackendQueryResult;
    } else if (eventName === "error") {
      streamError = String(data.message || "AI助教暂时不可用，请稍后重试。");
    }
  };

  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const blocks = buffer.split(/\n\n/);
      buffer = blocks.pop() || "";
      for (const block of blocks) {
        consumeBlock(block);
      }
      if (done) break;
    }
    if (buffer.trim()) {
      consumeBlock(buffer);
    }
  } catch (error) {
    throw new HttpError("流式响应解析失败", { status: response.status, details: error });
  }

  if (streamError) {
    throw new HttpError(streamError, { status: response.status });
  }
  if (!finalResult) {
    throw new HttpError("流式响应未返回最终答案", { status: response.status });
  }
  return finalResult;
}

export const aiService = {
  async getStudentConversations(): Promise<AiConversation[]> {
    return shouldUseMockApi
      ? getMockConversations("student")
      : (await http<BackendSession[]>("/chat/sessions")).map((item) =>
          normalizeConversation(item),
        );
  },

  async getTeacherConversations(): Promise<AiConversation[]> {
    return shouldUseMockApi
      ? getMockConversations("teacher")
      : (await http<BackendSession[]>("/chat/sessions")).map((item) =>
          normalizeConversation(item),
        );
  },

  async getConversationMessages(
    role: ConversationRole,
    conversationId: number,
  ): Promise<AiMessage[]> {
    return shouldUseMockApi
      ? getMockConversationMessages(role, conversationId)
      : (
          await http<BackendMessage[]>(
            `/chat/sessions/${sessionIdMap.get(conversationId) || conversationId}/messages`,
          )
        ).map(normalizeMessage);
  },

  async createConversation(
    role: ConversationRole,
    payload: CreateConversationPayload,
  ): Promise<AiConversation> {
    return shouldUseMockApi
      ? mockCreateConversation(role, payload)
      : {
          id: Date.now(),
          title: payload.title || "新对话",
          createdAt: new Date().toISOString(),
          lastMessage: "",
          messages: [],
        };
  },

  async deleteConversation(
    role: ConversationRole,
    conversationId: number,
  ): Promise<void> {
    if (shouldUseMockApi) {
      await mockDeleteConversation(role, conversationId);
      return;
    }

    void role;
    const backendId = sessionIdMap.get(conversationId);
    if (!backendId) return;
    await http<void>(`/chat/sessions/${backendId}`, { method: "DELETE" });
    sessionIdMap.delete(conversationId);
    reverseSessionIdMap.delete(backendId);
  },

  async sendMessage(
    role: ConversationRole,
    payload: SendMessagePayload,
  ): Promise<{ conversation: AiConversation; reply: AiMessage }> {
    if (shouldUseMockApi) {
      return mockSendMessage(role, payload);
    }

    const localConversationId = payload.conversationId || Date.now();
    const backendSessionId = payload.conversationId
      ? sessionIdMap.get(payload.conversationId)
      : undefined;
    const attachments = await uploadLiveAttachments(payload.attachments, payload.classId);
    const requestBody: BackendQueryRequest = {
      class_id: payload.classId,
      course_id: payload.courseId,
      session_id: backendSessionId,
      message: payload.content,
      answer_mode: payload.answerMode ?? "auto",
      attachments: attachments.map((attachment) => ({
        id: attachment.id,
        name: attachment.name,
        size: attachment.size,
        mime_type: attachment.mimeType,
        file_type: attachment.fileType,
        storage_key: attachment.storageKey || attachment.id,
      })),
    };
    const result = payload.onProgress
      ? await streamChatQuery(requestBody, payload.onProgress)
      : await http<BackendQueryResult>("/chat/query", {
          method: "POST",
          body: requestBody,
        });

    if (result.session_id) {
      sessionIdMap.set(localConversationId, result.session_id);
      reverseSessionIdMap.set(result.session_id, localConversationId);
    }

    const reply: AiMessage = {
      id: Math.abs(hashString(result.message_id || `${Date.now()}`)),
      role: "ai",
      content: result.content || "",
      time: new Date().toISOString(),
      sources: result.sources?.map(normalizeSource),
      confidence: result.confidence,
      quality: result.quality,
      reviewContext: result.review_context,
      routeMeta: normalizeRouteMeta(result.route_meta ?? {
        answer_mode: result.answer_mode,
        route: result.resolved_route,
        retrieval_used: result.retrieval_used,
        source_policy: result.source_policy,
      }),
      needsReview: result.needs_review,
    };
    if (result.message_id) {
      messageIdMap.set(reply.id, result.message_id);
    }
    const conversation: AiConversation = {
      id: localConversationId,
      backendSessionId: result.session_id,
      title: payload.content.slice(0, 24) || "附件问答",
      createdAt: new Date().toISOString(),
      lastMessage: reply.content.slice(0, 40),
      messages: [],
    };

    return { conversation, reply };
  },

  async uploadAttachment(file: AiAttachment): Promise<AiAttachment> {
    return shouldUseMockApi
      ? mockUploadAttachment(file)
      : (await uploadLiveAttachments([file]))[0];
  },

  async likeMessage(messageId: number): Promise<void> {
    if (shouldUseMockApi) {
      await mockLikeMessage();
      return;
    }

    await http<void>(`/chat/messages/${messageIdMap.get(messageId) || messageId}/feedback`, {
      method: "POST",
      body: { feedback: "like" },
    });
  },

  async dislikeMessage(messageId: number, reason?: string): Promise<void> {
    if (shouldUseMockApi) {
      await mockDislikeMessage();
      return;
    }

    await http<void>(`/chat/messages/${messageIdMap.get(messageId) || messageId}/feedback`, {
      method: "POST",
      body: { feedback: "dislike", reason },
    });
  },

  async submitFeedback(payload: SubmitFeedbackPayload): Promise<void> {
    if (shouldUseMockApi) {
      await mockSubmitFeedback(payload);
      return;
    }

    await http<void>("/ai/feedback", {
      method: "POST",
      body: payload,
    });
  },

  async escalateToTeacher(payload: SubmitFeedbackPayload): Promise<void> {
    if (shouldUseMockApi) {
      await mockEscalateToTeacher();
      return;
    }

    await http<void>("/ai/escalate", {
      method: "POST",
      body: payload,
    });
  },

  async getRecommendations(): Promise<AiResourceRecommendation[]> {
    return shouldUseMockApi
      ? getMockRecommendations()
      : http<AiResourceRecommendation[]>("/ai/recommendations");
  },

  async getMessageSources(messageId: number): Promise<AiMessageSource[]> {
    if (shouldUseMockApi) {
      return getMockMessageSources();
    }

    const sources = await http<BackendMessage["sources"]>(`/ai/messages/${messageId}/sources`);
    return (sources ?? []).map(normalizeSource);
  },

  async updateConversationContext(
    payload: ConversationContextPayload,
  ): Promise<void> {
    if (shouldUseMockApi) {
      await mockUpdateConversationContext(payload);
      return;
    }

    await http<void>("/ai/context", {
      method: "PATCH",
      body: payload,
    });
  },

  async updateConversationStyle(
    payload: ConversationStylePayload,
  ): Promise<void> {
    if (shouldUseMockApi) {
      await mockUpdateConversationStyle(payload);
      return;
    }

    await http<void>("/ai/style", {
      method: "PATCH",
      body: payload,
    });
  },

  async getTeacherAiQuestions(): Promise<AiTeacherQuestion[]> {
    return shouldUseMockApi
      ? getMockTeacherAiQuestions()
      : http<AiTeacherQuestion[]>("/teacher/ai/questions");
  },

  async getTeacherAiQuestionDetail(questionId: number): Promise<AiTeacherQuestion> {
    return shouldUseMockApi
      ? getMockTeacherAiQuestionDetail(questionId)
      : http<AiTeacherQuestion>(`/teacher/ai/questions/${questionId}`);
  },

  async replyAiQuestion(payload: ReplyAiQuestionPayload): Promise<void> {
    if (shouldUseMockApi) {
      await mockReplyAiQuestion(payload);
      return;
    }

    await http<void>("/teacher/ai/questions/reply", {
      method: "POST",
      body: payload,
    });
  },

  async adoptAiAnswer(questionId: number): Promise<void> {
    if (shouldUseMockApi) {
      await mockAdoptAiAnswer(questionId);
      return;
    }

    await http<void>(`/teacher/ai/questions/${questionId}/adopt`, {
      method: "POST",
    });
  },

  async getFeedbackQueue(classId?: string): Promise<AiFeedbackItem[]> {
    return shouldUseMockApi
      ? getMockFeedbackQueue()
      : (await http<BackendReviewItem[]>("/reviews/pending", {
          query: { class_id: classId, include_auto: false },
        })).map(normalizeFeedbackItem);
  },

  async resolveFeedback(
    feedbackId: string,
    teacherAnswer?: string,
    addToKb: boolean = true,
  ): Promise<{ sync_status?: string; sync_note?: string } | void> {
    if (shouldUseMockApi) {
      await mockResolveFeedback(feedbackId);
      return;
    }

    return http<{ sync_status?: string; sync_note?: string }>(`/reviews/${feedbackId}/submit`, {
      method: "POST",
      body: {
        teacher_answer: teacherAnswer,
        add_to_kb: addToKb,
      },
    });
  },

  async generateLessonPlan(
    payload: GenerateTeacherToolPayload,
  ): Promise<string> {
    return shouldUseMockApi
      ? mockGenerateLessonPlan(payload)
      : http<string>("/teacher/ai/tools/lesson-plan", {
          method: "POST",
          body: payload,
        });
  },

  async generateExam(payload: GenerateTeacherToolPayload): Promise<string> {
    return shouldUseMockApi
      ? mockGenerateExam(payload)
      : http<string>("/teacher/ai/tools/exam", {
          method: "POST",
          body: payload,
        });
  },

  async generateLearningAnalysis(
    payload: GenerateTeacherToolPayload,
  ): Promise<string> {
    return shouldUseMockApi
      ? mockGenerateLearningAnalysis(payload)
      : http<string>("/teacher/ai/tools/learning-analysis", {
          method: "POST",
          body: payload,
        });
  },

  async generateFlashcards(
    payload: GenerateTeacherToolPayload,
  ): Promise<string> {
    return shouldUseMockApi
      ? mockGenerateFlashcards(payload)
      : http<string>("/teacher/ai/tools/flashcards", {
          method: "POST",
          body: payload,
        });
  },
};
