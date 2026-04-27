import { shouldUseMockApi } from "@/lib/env";
import { http } from "@/lib/http";
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
  LearningOverviewData,
  LearningMistake,
  LearningMistakesData,
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

    await http<void>(`/student/courses/${courseId}/learning/export`, {
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
    mistakeId: number,
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
