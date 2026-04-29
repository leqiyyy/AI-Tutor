import { shouldUseMockApi } from "@/lib/env";
import { http } from "@/lib/http";
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
  attachments?: AiAttachment[];
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
    chunk_id?: string;
    chunkId?: string;
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
  needs_review?: boolean;
};

type BackendAttachment = {
  id?: string;
  storage_key?: string;
  name?: string;
  size?: number;
  mime_type?: string;
  file_type?: AiAttachment["fileType"];
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
    snippet: source.snippet,
    rawText: source.raw_text ?? source.rawText,
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
    attachments: message.attachments,
    sources: message.sources?.map(normalizeSource),
    confidence: message.confidence,
    quality: message.quality,
    reviewContext: message.review_context,
    needsReview: message.needs_review,
    feedback: message.feedback,
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

    await http<void>(
      `${conversationBasePath(role)}/conversations/${conversationId}`,
      {
        method: "DELETE",
      },
    );
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
    const result = await http<BackendQueryResult>("/chat/query", {
      method: "POST",
      body: {
        class_id: payload.classId,
        course_id: payload.courseId,
        session_id: backendSessionId,
        message: payload.content,
        attachments: attachments.map((attachment) => ({
          id: attachment.id,
          name: attachment.name,
          size: attachment.size,
          mime_type: attachment.mimeType,
          file_type: attachment.fileType,
          storage_key: attachment.storageKey || attachment.id,
        })),
      },
    });

    if (result.session_id) {
      sessionIdMap.set(localConversationId, result.session_id);
      reverseSessionIdMap.set(result.session_id, localConversationId);
    }

    const userMessage: AiMessage = {
      id: Date.now(),
      role: "user",
      content: payload.content,
      time: new Date().toISOString(),
      attachments,
    };
    const reply: AiMessage = {
      id: Math.abs(hashString(result.message_id || `${Date.now()}`)),
      role: "ai",
      content: result.content || "",
      time: new Date().toISOString(),
      sources: result.sources?.map(normalizeSource),
      confidence: result.confidence,
      quality: result.quality,
      reviewContext: result.review_context,
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
      messages: [userMessage, reply],
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

  async dislikeMessage(messageId: number): Promise<void> {
    if (shouldUseMockApi) {
      await mockDislikeMessage();
      return;
    }

    await http<void>(`/chat/messages/${messageIdMap.get(messageId) || messageId}/feedback`, {
      method: "POST",
      body: { feedback: "dislike" },
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

  async getFeedbackQueue(): Promise<AiFeedbackItem[]> {
    return shouldUseMockApi
      ? getMockFeedbackQueue()
      : http<AiFeedbackItem[]>("/teacher/ai/feedback");
  },

  async resolveFeedback(feedbackId: string): Promise<void> {
    if (shouldUseMockApi) {
      await mockResolveFeedback(feedbackId);
      return;
    }

    await http<void>(`/teacher/ai/feedback/${feedbackId}/resolve`, {
      method: "POST",
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
