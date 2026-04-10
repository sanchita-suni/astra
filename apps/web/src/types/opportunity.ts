/**
 * TypeScript mirror of `packages/schemas/astra_schemas/opportunity.py`.
 *
 * This file is hand-maintained on Day 1 and should be regenerated from Pydantic
 * via `pydantic2ts` (see `packages/schemas`) starting Day 2 — once the schema
 * evolves we don't want to drift between Python and TS.
 */

export type OpportunityType = "Hackathon" | "Internship" | "Fellowship" | "Grant";
export type OpportunityMode = "Remote" | "In-Person" | "Hybrid";
export type ComplexityRatio = "Low" | "Medium" | "High";
export type ResourceType = "Video" | "Doc" | "Repo" | "Course" | "Article";

export interface Resource {
  type: ResourceType;
  title: string;
  url: string;
}

export interface BridgeRoadmapDay {
  day: number;
  focus: string;
  resources: Resource[];
}

export interface ReadinessEngine {
  skill_gap_identified: string[];
  bridge_roadmap: BridgeRoadmapDay[];
}

export interface SuperTeamMember {
  user_id: string;
  name: string;
  role_filled: string;
  compatibility_score: number;
}

export interface TeammateMatchmaker {
  suggested_super_team: SuperTeamMember[];
}

export interface Metadata {
  title: string;
  organization: string;
  source: string;
  type: OpportunityType;
  mode: OpportunityMode;
  deadline_iso: string; // ISO datetime string
  apply_link: string;
  raw_requirements: string[];
}

export interface MatchAnalysis {
  overall_fit_percentage: number;
  semantic_overlap_score: number;
  user_trust_score: number;
  ai_reasoning: string;
}

export interface ExecutionIntel {
  complexity_to_time_ratio: ComplexityRatio;
  estimated_hours_required: number;
  recommended_start_date_iso: string;
  deadman_switch_alert: string;
}

export interface Opportunity {
  opportunity_id: string;
  metadata: Metadata;
  match_analysis: MatchAnalysis;
  execution_intel: ExecutionIntel;
  readiness_engine: ReadinessEngine;
  teammate_matchmaker: TeammateMatchmaker;
}
