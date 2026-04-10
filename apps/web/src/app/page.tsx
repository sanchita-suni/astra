"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { Opportunity } from "@/types/opportunity";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function HomePage() {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/opportunities`, {
      credentials: "include",  // sends auth cookie for per-user scoring
      cache: "no-store",
      headers: { Accept: "application/json" },
    })
      .then(async (res) => {
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        const data = await res.json();
        setOpportunities(data);
      })
      .catch((err) => setApiError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      <main className="mx-auto max-w-4xl px-6 py-12">
        <header className="mb-12">
          <p className="mb-2 text-sm font-medium tracking-wider text-indigo-600 uppercase dark:text-indigo-400">
            Astra
          </p>
          <h1 className="text-4xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50 sm:text-5xl">
            Opportunity, On-Target.
          </h1>
          <p className="mt-4 max-w-2xl text-lg text-zinc-600 dark:text-zinc-400">
            Multi-agent AI hackathon co-pilot. Doesn&apos;t just{" "}
            <em>list</em> hackathons — closes your skill gap, scaffolds your
            starter repo, and rehearses you for demo day.
          </p>
        </header>

        <section>
          <h2 className="mb-4 text-sm font-semibold tracking-wider text-zinc-500 uppercase">
            {loading ? "Loading..." : `Open hackathons (${opportunities.length})`}
          </h2>

          {apiError ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
              <p className="font-medium">API unreachable</p>
              <p className="mt-1 font-mono text-xs">{apiError}</p>
            </div>
          ) : loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-24 animate-pulse rounded-lg border border-zinc-200 bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-900" />
              ))}
            </div>
          ) : (
            <ul className="space-y-3">
              {opportunities.map((opp) => {
                const fit = opp.match_analysis.overall_fit_percentage;
                const fitColor = fit >= 60 ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200"
                  : fit >= 40 ? "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200"
                  : fit > 0 ? "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200"
                  : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400";
                const deadline = new Date(opp.metadata.deadline_iso);
                const daysLeft = Math.max(0, Math.ceil((deadline.getTime() - Date.now()) / 86400000));

                return (
                  <li
                    key={opp.opportunity_id}
                    className="rounded-lg border border-zinc-200 bg-white p-5 transition-colors hover:border-indigo-300 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-indigo-700"
                  >
                    <Link
                      href={`/opportunity/${encodeURIComponent(opp.opportunity_id)}`}
                      className="block"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <h3 className="text-lg font-medium text-zinc-900 dark:text-zinc-50">
                            {opp.metadata.title}
                          </h3>
                          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                            {opp.metadata.organization} · {opp.metadata.source} ·{" "}
                            {opp.metadata.mode} · {daysLeft > 0 ? `${daysLeft}d left` : "Ended"}
                          </p>
                          {opp.metadata.raw_requirements.length > 0 && (
                            <div className="mt-2 flex flex-wrap gap-1">
                              {opp.metadata.raw_requirements.slice(0, 5).map((r) => (
                                <span
                                  key={r}
                                  className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
                                >
                                  {r}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                        <span className={`shrink-0 rounded-full px-3 py-1 text-sm font-medium ${fitColor}`}>
                          {fit}% fit
                        </span>
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}
