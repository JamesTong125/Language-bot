export type CefrLevel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2";

export interface Language {
  code: string;
  name: string;
  native_name: string;
  speech_tag: string;
}

export interface LanguagesResponse {
  languages: Language[];
  cefr_levels: CefrLevel[];
}

export interface User {
  id: number;
  email: string;
  native_language: string | null;
}

export interface LearnerProfile {
  id: number;
  target_language: string;
  cefr_level: CefrLevel;
  goals: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProfileResponse {
  email: string;
  native_language: string | null;
  current: LearnerProfile | null;
  profiles: LearnerProfile[];
}

export interface Scenario {
  id: number;
  title: string;
  description: string;
  partner_persona: string;
  goal: string;
  target_language: string | null;
  cefr_level: CefrLevel;
  is_custom: boolean;
}

export type ErrorType =
  | "grammar"
  | "vocabulary"
  | "spelling"
  | "word_order"
  | "conjugation"
  | "register";

export interface Correction {
  id: number;
  original: string;
  corrected: string;
  error_type: ErrorType;
  explanation: string;
  severity: 1 | 2 | 3;
}

export interface Turn {
  id: number;
  role: "learner" | "partner";
  text: string;
  created_at: string;
  corrections: Correction[];
}

export interface CorrectionsEvent {
  turn_id: number;
  status: "ok" | "failed";
  corrections: Correction[];
}

export interface PracticeSession {
  id: number;
  scenario: Scenario;
  target_language: string;
  native_language: string;
  cefr_level: CefrLevel;
  is_private: boolean;
  started_at: string;
  ended_at: string | null;
  summary: string | null;
  turns: Turn[];
}

export interface Hint {
  suggestions: string[];
}

export interface ProfileUpdate {
  native_language: string;
  target_language: string;
  cefr_level: CefrLevel;
  goals: string | null;
}

export interface VocabItem {
  id: number;
  term: string;
  translation: string;
  example_sentence: string | null;
  source_correction_id: number | null;
  session_id: number | null;
  ease: number;
  interval_days: number;
  repetitions: number;
  due_at: string;
  created_at: string;
}

export type VocabFilter = "all" | "due" | "new" | "learning" | "mistakes";

export interface VocabPage {
  items: VocabItem[];
  total: number;
  page: number;
  page_size: number;
  due_count: number;
}

export interface ReviewQueue {
  items: VocabItem[];
  due_count: number;
}

export interface SessionSummary {
  went_well: string;
  recurring_mistakes: string[];
  practice: string[];
}

export interface WrapUpResult {
  session_id: number;
  summary: SessionSummary | null;
  error_rate: number | null;
  new_vocab: VocabItem[];
  skipped_duplicates: number;
}
export interface ScenarioList {
  scenarios: Scenario[];
  private_available: boolean;
}

export interface LevelProgress {
  current_level: CefrLevel;
  direction: "up" | "down" | null;
  suggested_level: CefrLevel | null;
  average_error_rate: number | null;
  sessions_counted: number;
  sessions_needed: number;
  session_ids: number[];
  up_threshold: number;
  down_threshold: number;
}

export interface Stats {
  time_zone: string;
  streak: { days: number; practised_today: boolean };
  totals: {
    sessions_completed: number;
    learner_messages: number;
    vocab_items: number;
    vocab_due: number;
    reviews: number;
  };
  sessions_per_week: { week_start: string; sessions: number }[];
  error_rate_trend: {
    session_id: number;
    ended_at: string;
    scenario_title: string;
    cefr_level: CefrLevel;
    error_rate: number;
  }[];
  error_types: { error_type: ErrorType; count: number }[];
  level: LevelProgress;
}