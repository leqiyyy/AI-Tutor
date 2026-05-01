import { shouldUseMockApi } from "@/lib/env";
import { getAuthSession } from "@/lib/auth-storage";
import { buildUrl, http } from "@/lib/http";
import {
  getMockFlashcardDecks,
  getMockLearningOverview,
  getMockMistakes,
  mockCreateFlashcardDeck,
  mockCreateMistake,
} from "@/mocks/learning";
import type {
  CreateFlashcardDeckRequest,
  CreateMistakeRequest,
  ExportLearningDataRequest,
  FlashcardDeck,
  FlashcardDecksData,
  LearningEventRequest,
  LearningOverviewData,
  LearningMistake,
  LearningMistakesData,
  LearningReportData,
  SubmitFlashcardReviewRequest,
} from "@/types/learning";

export const learningService = {
  async getLearningOverview(courseId: string): Promise<LearningOverviewData> {
    return shouldUseMockApi
      ? getMockLearningOverview()
      : http<LearningOverviewData>(`/student/courses/${courseId}/learning/overview`);
  },

  async exportLearningData(
    courseId: string,
    payload: ExportLearningDataRequest,
  ): Promise<void> {
    if (shouldUseMockApi) return;

    const session = getAuthSession();
    const response = await fetch(buildUrl(`/student/courses/${courseId}/learning/export`, {
      period: payload.period || "weekly",
      format: payload.format || "csv",
    }), {
      method: "GET",
      headers: session?.accessToken
        ? { Authorization: `Bearer ${session.accessToken}` }
        : undefined,
      credentials: "include",
    });
    if (!response.ok) throw new Error("导出学习数据失败");
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `learning-${payload.period || "weekly"}-report.${payload.format || "csv"}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },

  async getLearningReport(
    courseId: string,
    period: "weekly" | "monthly",
  ): Promise<LearningReportData> {
    return shouldUseMockApi
      ? {
          period,
          title: period === "weekly" ? "学习周报" : "学习月报",
          rangeLabel: period === "weekly" ? "本周" : "本月",
          generatedAt: new Date().toISOString(),
          summary: "模拟报告数据",
          cards: [],
          metrics: {
            studyHours: 0,
            questionCount: 0,
            taskCompleted: 0,
            taskPublished: 0,
            taskCompletionRate: 0,
            flashcardReviews: 0,
            mistakeCount: 0,
            masteredMistakeCount: 0,
            learningEvents: 0,
          },
          weakTopics: [],
          strongTopics: [],
          suggestions: [],
          highlights: [],
        }
      : http<LearningReportData>(`/student/courses/${courseId}/learning/report`, {
          query: { period },
        });
  },

  async recordLearningEvent(
    courseId: string,
    payload: LearningEventRequest,
  ): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/student/courses/${courseId}/learning/events`, {
      method: "POST",
      body: payload,
    });
  },

  async getMistakes(courseId: string): Promise<LearningMistakesData> {
    return shouldUseMockApi
      ? getMockMistakes()
      : http<LearningMistakesData>(`/student/courses/${courseId}/learning/mistakes`);
  },

  async createMistake(
    courseId: string,
    payload: CreateMistakeRequest,
  ): Promise<LearningMistake> {
    return shouldUseMockApi
      ? mockCreateMistake(payload)
      : http<LearningMistake>(`/student/courses/${courseId}/learning/mistakes`, {
          method: "POST",
          body: payload,
        });
  },

  async markMistakeMastered(
    courseId: string,
    mistakeId: string | number,
  ): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(
      `/student/courses/${courseId}/learning/mistakes/${mistakeId}/mastered`,
      {
        method: "POST",
      },
    );
  },

  async getFlashcardDecks(courseId: string): Promise<FlashcardDecksData> {
    return shouldUseMockApi
      ? getMockFlashcardDecks()
      : http<FlashcardDecksData>(`/student/courses/${courseId}/learning/flashcards`);
  },

  async createFlashcardDeck(
    courseId: string,
    payload: CreateFlashcardDeckRequest,
  ): Promise<FlashcardDeck> {
    return shouldUseMockApi
      ? mockCreateFlashcardDeck(payload)
      : http<FlashcardDeck>(
          `/student/courses/${courseId}/learning/flashcards/decks`,
          {
            method: "POST",
            body: payload,
          },
        );
  },

  async submitFlashcardReview(
    courseId: string,
    payload: SubmitFlashcardReviewRequest,
  ): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/student/courses/${courseId}/learning/flashcards/reviews`, {
      method: "POST",
      body: payload,
    });
  },
};
