export type ExperienceLevel = "beginner" | "intermediate" | "advanced";
export type HackathonType = "ai-ml" | "web" | "mobile" | "hardware" | "blockchain" | "data" | "social-impact" | "open";
export type TimeAvailability = "5" | "10" | "15" | "20" | "30" | "40+";

export interface QuestionnaireResponse {
  experience_level: ExperienceLevel;
  preferred_types: HackathonType[];
  skills_to_learn: string[];
  hours_per_week: TimeAvailability;
}

export interface ResumeSkills {
  skills: string[];
  education: string[];
  experience_summary: string;
  extraction_source: "keyword" | "llm";
}

export interface UserProfile {
  user_id: string;
  github_login: string;
  github_name: string | null;
  github_avatar_url: string | null;
  email: string | null;
  questionnaire: QuestionnaireResponse | null;
  resume: ResumeSkills | null;
  created_at: string;
  updated_at: string;
}
