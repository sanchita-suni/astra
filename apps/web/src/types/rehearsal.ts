export type JudgePersona = "industry" | "academic" | "vc";

export interface RubricBreakdown {
  feasibility: number;
  novelty: number;
  market_fit: number;
  polish: number;
}

export interface JudgeScore {
  judge: JudgePersona;
  judge_name: string;
  rubric: RubricBreakdown;
  score: number;
  feedback: string;
}

export interface DryRunRubric {
  opportunity_id: string;
  pitch: string;
  repo_url: string | null;
  scores: JudgeScore[];
  overall_score: number;
  overall_feedback: string;
  generated_at: string;
  rubric_source: "llm" | "fallback";
}
