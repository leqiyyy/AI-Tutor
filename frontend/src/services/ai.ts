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

export const aiService = {
  async getStudentConversations(): Promise<AiConversation[]> {
    return shouldUseMockApi
      ? getMockConversations("student")
      : http<AiConversation[]>("/student/ai/conversations");
  },

  async getTeacherConversations(): Promise<AiConversation[]> {
    return shouldUseMockApi
      ? getMockConversations("teacher")
      : http<AiConversation[]>("/teacher/ai/conversations");
  },

  async getConversationMessages(
    role: ConversationRole,
    conversationId: number,
  ): Promise<AiMessage[]> {
    return shouldUseMockApi
      ? getMockConversationMessages(role, conversationId)
      : http<AiMessage[]>(
          `${conversationBasePath(role)}/conversations/${conversationId}/messages`,
        );
  },

  async createConversation(
    role: ConversationRole,
    payload: CreateConversationPayload,
  ): Promise<AiConversation> {
    return shouldUseMockApi
      ? mockCreateConversation(role, payload)
      : http<AiConversation>(`${conversationBasePath(role)}/conversations`, {
          method: "POST",
          body: payload,
        });
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
    return shouldUseMockApi
      ? mockSendMessage(role, payload)
      : http<{ conversation: AiConversation; reply: AiMessage }>(
          `${conversationBasePath(role)}/messages`,
          {
            method: "POST",
            body: payload,
          },
        );
  },

  async uploadAttachment(file: AiAttachment): Promise<AiAttachment> {
    return shouldUseMockApi
      ? mockUploadAttachment(file)
      : http<AiAttachment>("/ai/attachments", {
          method: "POST",
          body: file,
        });
  },

  async likeMessage(messageId: number): Promise<void> {
    if (shouldUseMockApi) {
      await mockLikeMessage();
      return;
    }

    await http<void>(`/ai/messages/${messageId}/like`, { method: "POST" });
  },

  async dislikeMessage(messageId: number): Promise<void> {
    if (shouldUseMockApi) {
      await mockDislikeMessage();
      return;
    }

    await http<void>(`/ai/messages/${messageId}/dislike`, { method: "POST" });
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
    return shouldUseMockApi
      ? getMockMessageSources()
      : http<AiMessageSource[]>(`/ai/messages/${messageId}/sources`);
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
