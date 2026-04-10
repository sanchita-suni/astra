"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import type { BridgeRoadmapDay, Opportunity } from "@/types/opportunity";
import { ScaffoldButton, RegisterButton } from "./action-buttons";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function OpportunityPage() {
  const params = useParams();
  const id = params.id as string;
  const [opp, setOpp] = useState<Opportunity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/opportunities/${encodeURIComponent(id)}`, {
      credentials: "include",
      cache: "no-store",
      headers: { Accept: "application/json" },
    })
      .then(async (res) => {
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        setOpp(await res.json());
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <p className="text-zinc-500 animate-pulse">Loading opportunity...</p>
      </div>
    );
  }

  if (error || !opp) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50 mb-2">Not found</h1>
          <p className="text-zinc-500">{error || "Opportunity not found"}</p>
          <Link href="/" className="mt-4 inline-block text-indigo-600 hover:underline">Back to feed</Link>
        </div>
      </div>
    );
  }

  const deadline = new Date(opp.metadata.deadline_iso);
  const startDate = new Date(opp.execution_intel.recommended_start_date_iso);
  const daysLeft = Math.max(0, Math.ceil((deadline.getTime() - Date.now()) / 86400000));

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      <main className="mx-auto max-w-4xl px-6 py-12">
        <header className="mb-10">
          <p className="mb-2 text-sm font-medium tracking-wider text-indigo-600 uppercase dark:text-indigo-400">
            {opp.metadata.source} &middot; {opp.metadata.type} &middot; {daysLeft > 0 ? `${daysLeft} days left` : "Deadline passed"}
          </p>
          <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50 sm:text-4xl">
            {opp.metadata.title}
          </h1>
          <p className="mt-2 text-lg text-zinc-600 dark:text-zinc-400">
            {opp.metadata.organization} &middot; {opp.metadata.mode}
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <a href={opp.metadata.apply_link} target="_blank" rel="noopener noreferrer" className="rounded-full bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500">
              Apply on {opp.metadata.source}
            </a>
            <Link href={`/opportunity/${encodeURIComponent(id)}/rehearsal`} className="rounded-full border border-indigo-600 px-4 py-2 text-sm font-medium text-indigo-600 hover:bg-indigo-50 dark:border-indigo-400 dark:text-indigo-400">
              Rehearse demo day
            </Link>
            <RegisterButton opportunityId={id} />
            <span className="text-sm text-zinc-500 dark:text-zinc-400">Deadline: {deadline.toLocaleDateString()}</span>
          </div>
        </header>

        {/* Match scores */}
        <section className="mb-10 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <ScoreCard label="Overall fit" value={opp.match_analysis.overall_fit_percentage} />
          <ScoreCard label="Semantic overlap" value={opp.match_analysis.semantic_overlap_score} />
          <ScoreCard label="Trust score" value={opp.match_analysis.user_trust_score} />
        </section>

        {/* AI reasoning */}
        {opp.match_analysis.ai_reasoning && opp.match_analysis.ai_reasoning !== "(pending analyst crew)" && (
          <Section title="Why it fits you">
            <p className="text-zinc-700 dark:text-zinc-300">{opp.match_analysis.ai_reasoning}</p>
          </Section>
        )}

        {/* Required stack */}
        {opp.metadata.raw_requirements.length > 0 && (
          <Section title="Required stack">
            <div className="flex flex-wrap gap-2">
              {opp.metadata.raw_requirements.map((req) => (
                <span key={req} className="rounded-full bg-indigo-100 px-3 py-1 text-sm font-medium text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200">{req}</span>
              ))}
            </div>
          </Section>
        )}

        {/* Execution intel */}
        <Section title="Execution intel">
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Complexity" value={opp.execution_intel.complexity_to_time_ratio} />
            <Field label="Estimated hours" value={`${opp.execution_intel.estimated_hours_required} h`} />
            <Field label="Recommended start" value={startDate.toLocaleDateString()} />
            <Field label="Days until deadline" value={`${daysLeft} days`} />
          </dl>
          {opp.execution_intel.deadman_switch_alert && opp.execution_intel.deadman_switch_alert !== "(pending deadman switch)" && (
            <div className="mt-4 rounded-lg border-l-4 border-amber-500 bg-amber-50 p-4 dark:bg-amber-950">
              <p className="text-sm font-medium text-amber-900 dark:text-amber-200">Deadman switch</p>
              <p className="mt-1 text-sm text-amber-800 dark:text-amber-300">{opp.execution_intel.deadman_switch_alert}</p>
            </div>
          )}
        </Section>

        {/* Skill gap + bridge roadmap */}
        <Section title="Bridge roadmap">
          {opp.readiness_engine.skill_gap_identified.length > 0 && (
            <div className="mb-4">
              <p className="mb-2 text-sm font-medium text-zinc-500 dark:text-zinc-400">Skills to learn</p>
              <div className="flex flex-wrap gap-2">
                {opp.readiness_engine.skill_gap_identified.map((skill) => (
                  <span key={skill} className="rounded-full bg-red-100 px-3 py-1 text-sm font-medium text-red-800 dark:bg-red-900 dark:text-red-200">{skill}</span>
                ))}
              </div>
            </div>
          )}
          {opp.readiness_engine.bridge_roadmap.length > 0 ? (
            <ol className="space-y-4">
              {opp.readiness_engine.bridge_roadmap.map((day) => (
                <BridgeDayItem key={day.day} day={day} />
              ))}
            </ol>
          ) : (
            <p className="text-sm text-emerald-600 dark:text-emerald-400">
              No skill gap detected — your profile already covers the requirements. Go build!
            </p>
          )}
        </Section>

        {/* Scaffold */}
        <Section title="Bridge-to-Build — starter repo">
          <p className="mb-4 text-sm text-zinc-600 dark:text-zinc-400">
            Generate a starter repo with a BRIEF.md tailored to this hackathon.
          </p>
          <ScaffoldButton opportunityId={id} />
        </Section>
      </main>
    </div>
  );
}

function ScoreCard({ label, value }: { label: string; value: number }) {
  const color = value >= 60 ? "text-emerald-600" : value >= 40 ? "text-amber-600" : value > 0 ? "text-indigo-600" : "text-zinc-500";
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <p className="text-xs font-medium tracking-wider text-zinc-500 uppercase">{label}</p>
      <p className={`mt-1 text-3xl font-semibold ${color}`}>{value}%</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-10">
      <h2 className="mb-4 text-sm font-semibold tracking-wider text-zinc-500 uppercase">{title}</h2>
      {children}
    </section>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900">
      <dt className="text-xs font-medium text-zinc-500 dark:text-zinc-400">{label}</dt>
      <dd className="mt-1 text-sm font-medium text-zinc-900 dark:text-zinc-50">{value}</dd>
    </div>
  );
}

function BridgeDayItem({ day }: { day: BridgeRoadmapDay }) {
  return (
    <li className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex items-baseline gap-3">
        <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-semibold text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200">Day {day.day}</span>
        <p className="text-base font-medium text-zinc-900 dark:text-zinc-50">{day.focus}</p>
      </div>
      <ul className="mt-3 space-y-1.5">
        {day.resources.map((res, idx) => (
          <li key={`${res.url}-${idx}`} className="flex items-center gap-2 text-sm">
            <span className={`shrink-0 rounded px-1.5 py-0.5 text-xs font-medium ${
              res.type === "Course" ? "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200" :
              res.type === "Video" ? "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200" :
              res.type === "Doc" ? "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200" :
              res.type === "Repo" ? "bg-zinc-200 text-zinc-800 dark:bg-zinc-700 dark:text-zinc-200" :
              "bg-zinc-100 text-zinc-600"
            }`}>{res.type}</span>
            <a href={res.url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline dark:text-indigo-400">{res.title}</a>
          </li>
        ))}
      </ul>
    </li>
  );
}
