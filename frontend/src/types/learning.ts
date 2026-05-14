export interface LearningMistake {
  id: string | number;
  question: string;
  chapter: string;
  wrongCount: number;
  myAnswer: string;
  correctAnswer: string;
  analysis: string;
  addTime: string;
  lastPracticeTime: string;
  mastered: boolean;
  source?: string;
  sourceTaskId?: string | number;
  sourceTaskTitle?: string;
  sourceTaskType?: string;
  sourceSubmissionId?: string | number;
  sourceQuestionId?: string | number;
}

export interface LearningMistakesData {
  mistakes: LearningMistake[];
}

export interface CreateMistakeRequest {
  question: string;
  chapter: string;
  myAnswer: string;
  correctAnswer: string;
  analysis: string;
}

export interface Flashcard {
  id?: string | number;
  front: string;
  back: string;
  due?: boolean;
  nextReviewAt?: string | null;
  reviewCount?: number;
}

export interface FlashcardDeck {
  id: string | number;
  name: string;
  cards: number;
  mastered: number;
  learning: number;
  new: number;
  dueCount?: number;
  nextReview: string;
  cardList: Flashcard[];
}

export interface FlashcardDecksData {
  decks: FlashcardDeck[];
}

export interface CreateFlashcardDeckRequest {
  name: string;
  cards: Flashcard[];
}

export interface SubmitFlashcardReviewRequest {
  deckId: string | number;
  cardIndex?: number;
  cardId?: string | number;
  difficulty: "forget" | "hard" | "good" | "easy";
}

export interface MistakePracticeData {
  mistakeId: string | number;
  prompt: string;
  answerHint: string;
  analysis: string;
  lastPracticeTime: string;
  mistake: LearningMistake;
}

export interface LearningSummaryCard {
  label: string;
  value: string;
  sub: string;
  icon: string;
  color: string;
  progress: number;
}

export interface LearningRadarItem {
  label: string;
  score: number;
  fullScore: number;
}

export interface LearningKeyword {
  word: string;
  count: number;
}

export interface WeeklyStudyHour {
  day: string;
  hours: number;
  date: string;
}

export interface ChapterProgress {
  name: string;
  progress: number;
  status: string;
}

export interface LearningOverviewData {
  summaryCards: LearningSummaryCard[];
  radarData: LearningRadarItem[];
  keywordData: LearningKeyword[];
  weekHours: WeeklyStudyHour[];
  chapterProgress: ChapterProgress[];
}

export interface ExportLearningDataRequest {
  format: string;
  period?: "weekly" | "monthly";
  fields: Record<string, boolean>;
}

export interface LearningReportCard {
  label: string;
  value: string;
  color: string;
}

export interface LearningReportData {
  period: "weekly" | "monthly";
  title: string;
  rangeLabel: string;
  generatedAt: string;
  summary: string;
  cards: LearningReportCard[];
  metrics: {
    studyHours: number;
    questionCount: number;
    taskCompleted: number;
    taskPublished: number;
    taskCompletionRate: number;
    flashcardReviews: number;
    mistakeCount: number;
    masteredMistakeCount: number;
    learningEvents: number;
  };
  weakTopics: string[];
  strongTopics: string[];
  suggestions: string[];
  highlights: string[];
}

export interface LearningEventRequest {
  activity_type: string;
  ref_id?: string;
  duration_seconds?: number;
  extra_data?: Record<string, unknown>;
}
