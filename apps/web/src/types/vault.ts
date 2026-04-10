/**
 * TypeScript mirror of `packages/schemas/astra_schemas/vault.py`.
 *
 * Hand-maintained alongside the Pydantic source for Day 3. Day 5 cleanup will
 * regenerate via `pydantic2ts` so the contract can't drift.
 */

export type VaultRelevance = "high" | "medium" | "low";

export interface VaultEntry {
  repo_full_name: string;
  repo_name: string;
  repo_url: string;
  language: string | null;
  stars: number;
  topics: string[];
  description: string | null;
  narrative: string;
  relevance: VaultRelevance;
}

export interface Vault {
  user_login: string;
  user_name: string | null;
  user_url: string;
  bio: string | null;
  total_stars: number;
  languages_top: string[];
  entries: VaultEntry[];
  generated_at: string; // ISO datetime string
  narration_source: "llm" | "fallback";
}
