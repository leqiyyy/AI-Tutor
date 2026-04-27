export interface LearningMistake {
  id: number;
  question: string;
  chapter: string;
  wrongCount: number;
  myAnswer: string;
  correctAnswer: string;
  analysis: string;
  addTime: string;
  lastPracticeTime: string;
  mastered: boolean;
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
  front: string;
  back: string;
}

export interface FlashcardDeck {
  id: number;
  name: string;
  cards: number;
  mastered: number;
  learning: number;
  new: number;
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
  deckId: number;
  cardIndex: number;
  difficulty: "forget" | "hard" | "good" | "easy";
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
  fields: Record<string, boolean>;
}
