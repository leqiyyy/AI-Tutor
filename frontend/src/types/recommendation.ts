export type RecommendationSurface =
  | "dashboard"
  | "ai_panel"
  | "my_learning"
  | "after_answer"
  | "report";

export type RecommendationType =
  | "material"
  | "concept"
  | "faq"
  | "mistake"
  | "flashcard"
  | "path"
  | "task"
  | "followup";

export interface PersonalizedRecommendation {
  id: string;
  targetId: string;
  type: RecommendationType | string;
  title: string;
  description: string;
  reason: string;
  relevance: number;
  score: number;
  surface: RecommendationSurface | string;
  action: {
    type: string;
    label: string;
    payload?: Record<string, unknown>;
  };
  evidence?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface PersonalizedRecommendationContext {
  surface: RecommendationSurface | string;
  surfaceLabel: string;
  courseId?: string;
  classId?: string;
  className?: string;
  weakTerms?: string[];
  recentTerms?: string[];
  algorithm?: string;
  generatedAt?: string;
}

export interface PersonalizedRecommendationData {
  items: PersonalizedRecommendation[];
  context: PersonalizedRecommendationContext;
}

export interface RecommendationEventRequest {
  recommendation_type: string;
  target_id: string;
  event_type: "impression" | "click" | "complete" | "dismiss" | string;
  class_id?: string;
  score?: number;
  extra_data?: Record<string, unknown>;
}
