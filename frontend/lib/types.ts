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

export interface ProfileUpdate {
  native_language: string;
  target_language: string;
  cefr_level: CefrLevel;
  goals: string | null;
}
