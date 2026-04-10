"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getUserVault } from "@/lib/api-client";
import type { Vault, VaultEntry, VaultRelevance } from "@/types/vault";
import SkillHeatmap from "./skill-heatmap";
import ProfileActions from "./profile-actions";

export default function ProfilePage() {
  const params = useParams();
  const login = params.login as string;
  const [vault, setVault] = useState<Vault | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getUserVault(login, { useLlm: false })
      .then(setVault)
      .catch((err) => setError(err.message || "Failed to load profile"))
      .finally(() => setLoading(false));
  }, [login]);

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <p className="text-zinc-500 dark:text-zinc-400 animate-pulse">Loading profile...</p>
      </div>
    );
  }

  if (error || !vault) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center max-w-md">
          <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50 mb-2">Profile not found</h1>
          <p className="text-zinc-500 dark:text-zinc-400">{error || `Could not load @${login}`}</p>
        </div>
      </div>
    );
  }

  const skillCounts: Record<string, number> = {};
  for (const entry of vault.entries) {
    if (entry.language) skillCounts[entry.language] = (skillCounts[entry.language] || 0) + 1;
    for (const topic of entry.topics) skillCounts[topic] = (skillCounts[topic] || 0) + 1;
  }
  const skills = Object.entries(skillCounts)
    .sort((a, b) => b[1] - a[1])
    .map(([name, count]) => ({ name, count, max: Math.max(...Object.values(skillCounts), 1) }));

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      <main className="mx-auto max-w-4xl px-6 py-12">
        <header className="mb-10">
          <div className="flex items-start gap-5">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-indigo-100 text-2xl font-bold text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300">
              {(vault.user_name || vault.user_login).charAt(0).toUpperCase()}
            </div>
            <div>
              <p className="mb-1 text-sm font-medium tracking-wider text-indigo-600 uppercase dark:text-indigo-400">Proof-of-Work Vault</p>
              <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">{vault.user_name ?? vault.user_login}</h1>
              {vault.bio && <p className="mt-1 text-zinc-600 dark:text-zinc-400">{vault.bio}</p>}
            </div>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
            <a href={vault.user_url} target="_blank" rel="noopener noreferrer" className="rounded-full bg-zinc-900 px-4 py-2 font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900">GitHub @{vault.user_login}</a>
            <span className="text-zinc-500 dark:text-zinc-400">{vault.entries.length} repos &middot; {vault.total_stars} stars</span>
            <a href="/onboarding" className="rounded-full border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800">Edit preferences</a>
          </div>
        </header>

        {skills.length > 0 && (
          <section className="mb-10">
            <h2 className="mb-4 text-sm font-semibold tracking-wider text-zinc-500 uppercase">Skill heatmap</h2>
            <SkillHeatmap skills={skills} />
          </section>
        )}

        {vault.languages_top.length > 0 && (
          <section className="mb-10">
            <h2 className="mb-4 text-sm font-semibold tracking-wider text-zinc-500 uppercase">Top languages</h2>
            <div className="space-y-2">
              {vault.languages_top.map((lang) => {
                const count = skillCounts[lang] || 1;
                const maxCount = Math.max(...vault.languages_top.map((l) => skillCounts[l] || 1));
                const pct = Math.round((count / maxCount) * 100);
                return (
                  <div key={lang} className="flex items-center gap-3">
                    <span className="w-24 text-sm font-medium text-zinc-700 dark:text-zinc-300">{lang}</span>
                    <div className="flex-1 h-3 rounded-full bg-zinc-200 dark:bg-zinc-800 overflow-hidden">
                      <div className="h-full rounded-full bg-indigo-500" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="text-xs text-zinc-500 w-8 text-right">{count}</span>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        <ProfileActions login={vault.user_login} />

        <section>
          <h2 className="mb-4 text-sm font-semibold tracking-wider text-zinc-500 uppercase">Highlighted projects</h2>
          {vault.entries.length === 0 ? (
            <p className="text-sm text-zinc-500 dark:text-zinc-400">No public repositories found.</p>
          ) : (
            <ul className="space-y-4">
              {vault.entries.map((entry) => (
                <VaultEntryCard key={entry.repo_full_name} entry={entry} />
              ))}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}

function VaultEntryCard({ entry }: { entry: VaultEntry }) {
  return (
    <li className="rounded-lg border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex items-start justify-between gap-4">
        <div>
          <a href={entry.repo_url} target="_blank" rel="noopener noreferrer" className="text-base font-medium text-zinc-900 hover:text-indigo-600 dark:text-zinc-50 dark:hover:text-indigo-400">{entry.repo_full_name}</a>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
            {entry.language && <span>{entry.language}</span>}
            <span>&middot;</span>
            <span>{entry.stars} stars</span>
            {entry.topics.length > 0 && <><span>&middot;</span><span>{entry.topics.slice(0, 4).join(", ")}</span></>}
          </div>
        </div>
        <RelevanceBadge relevance={entry.relevance} />
      </div>
      <p className="mt-3 text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">{entry.narrative}</p>
    </li>
  );
}

function RelevanceBadge({ relevance }: { relevance: VaultRelevance }) {
  const styles: Record<VaultRelevance, string> = {
    high: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200",
    medium: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
    low: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  };
  return <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium ${styles[relevance]}`}>{relevance}</span>;
}
