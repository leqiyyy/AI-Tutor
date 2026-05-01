import { shouldUseMockApi } from "@/lib/env";
import { http } from "@/lib/http";
import type {
  PersonalizedRecommendationData,
  RecommendationEventRequest,
  RecommendationSurface,
} from "@/types/recommendation";

const EMPTY_RECOMMENDATIONS: PersonalizedRecommendationData = {
  items: [],
  context: {
    surface: "dashboard",
    surfaceLabel: "个性化推荐",
  },
};

export const recommendationService = {
  async getPersonalized(
    courseId: string | undefined,
    surface: RecommendationSurface,
    options: { limit?: number; query?: string } = {},
  ): Promise<PersonalizedRecommendationData> {
    if (shouldUseMockApi || !courseId) {
      return EMPTY_RECOMMENDATIONS;
    }

    return http<PersonalizedRecommendationData>("/recommendations/personalized", {
      query: {
        course_id: courseId,
        surface,
        limit: options.limit ?? 6,
        query: options.query,
      },
    });
  },

  async recordEvent(payload: RecommendationEventRequest): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>("/recommendations/events", {
      method: "POST",
      body: payload,
    });
  },
};
