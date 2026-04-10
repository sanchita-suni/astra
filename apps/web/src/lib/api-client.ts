/**
 * Astra API client — typed fetch wrapper.
 *
 * Server Components call these directly. Keep this file dependency-free —
 * no react, no swr, no fancy state libs. The fetch boundary is the only
 * place that touches the backend.
 */

import type { Opportunity } from "@/types/opportunity";
import type { DryRunRubric } from "@/types/rehearsal";
import type { ScaffoldResult } from "@/types/scaffold";
import type { UserProfile, QuestionnaireResponse, ResumeSkills } from "@/types/user";
import type { Vault } from "@/types/vault";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class AstraApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly url: string,
    message: string,
  ) {
    super(message);
    this.name = "AstraApiError";
  }
}

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const res = await fetch(url, {
    // Day 1: don't cache. Day 2+ may opt into Next's `cache: 'force-cache'`
    // for opportunity reads since they update at most once per scrape cycle.
    cache: "no-store",
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    throw new AstraApiError(res.status, url, `${res.status} ${res.statusText} for ${path}`);
  }
  return (await res.json()) as T;
}

export async function getOpportunity(opportunityId: string): Promise<Opportunity> {
  return getJson<Opportunity>(`/opportunities/${encodeURIComponent(opportunityId)}`);
}

export async function listOpportunities(): Promise<Opportunity[]> {
  return getJson<Opportunity[]>("/opportunities");
}

export async function getUserVault(
  login: string,
  options: { useLlm?: boolean } = {},
): Promise<Vault> {
  const { useLlm = false } = options;
  const qs = `?use_llm=${useLlm ? "true" : "false"}`;
  return getJson<Vault>(`/users/${encodeURIComponent(login)}/vault${qs}`);
}

export async function postScaffold(
  opportunityId: string,
  options: { dryRun?: boolean; repoName?: string; useLlm?: boolean } = {},
): Promise<ScaffoldResult> {
  const { dryRun = true, repoName, useLlm = false } = options;
  const params = new URLSearchParams({ dry_run: String(dryRun), use_llm: String(useLlm) });
  if (repoName) params.set("repo_name", repoName);
  const url = `${API_BASE_URL}/opportunities/${encodeURIComponent(opportunityId)}/scaffold?${params}`;
  const res = await fetch(url, {
    method: "POST",
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new AstraApiError(res.status, url, `${res.status} ${res.statusText}`);
  return (await res.json()) as ScaffoldResult;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export async function getMe(): Promise<UserProfile | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/me`, {
      credentials: "include",
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return null;
    return (await res.json()) as UserProfile | null;
  } catch {
    return null;
  }
}

export async function logout(): Promise<void> {
  await fetch(`${API_BASE_URL}/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}

// ---------------------------------------------------------------------------
// Questionnaire + Resume + Feed
// ---------------------------------------------------------------------------

export async function updateQuestionnaire(q: QuestionnaireResponse): Promise<UserProfile> {
  const url = `${API_BASE_URL}/users/me/questionnaire`;
  const res = await fetch(url, {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(q),
  });
  if (!res.ok) throw new AstraApiError(res.status, url, `${res.status}`);
  return (await res.json()) as UserProfile;
}

export async function uploadResume(file: File): Promise<ResumeSkills> {
  const url = `${API_BASE_URL}/users/me/resume`;
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(url, {
    method: "POST",
    credentials: "include",
    headers: { Accept: "application/json" },
    body: form,
  });
  if (!res.ok) throw new AstraApiError(res.status, url, `${res.status}`);
  return (await res.json()) as ResumeSkills;
}

export async function getMyFeed(): Promise<Array<{ opportunity: Opportunity; match_score: number }>> {
  const url = `${API_BASE_URL}/users/me/feed`;
  const res = await fetch(url, {
    credentials: "include",
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) return [];
  return (await res.json()) as Array<{ opportunity: Opportunity; match_score: number }>;
}

export async function postDryRun(
  opportunityId: string,
  pitch: string,
  options: { repoUrl?: string; useLlm?: boolean } = {},
): Promise<DryRunRubric> {
  const { repoUrl, useLlm = false } = options;
  const params = new URLSearchParams({ use_llm: String(useLlm) });
  const url = `${API_BASE_URL}/opportunities/${encodeURIComponent(opportunityId)}/dry-run?${params}`;
  const body: Record<string, unknown> = { pitch };
  if (repoUrl) body.repo_url = repoUrl;
  const res = await fetch(url, {
    method: "POST",
    cache: "no-store",
    headers: { "Accept": "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new AstraApiError(res.status, url, `${res.status} ${res.statusText}`);
  return (await res.json()) as DryRunRubric;
}
