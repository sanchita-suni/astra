"use client";

import { useState } from "react";
import type { DryRunRubric, JudgeScore, JudgePersona } from "@/types/rehearsal";
import { postDryRun } from "@/lib/api-client";

interface Props {
  opportunityId: string;
}

export default function RehearsalForm({ opportunityId }: Props) {
  const [pitch, setPitch] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rubric, setRubric] = useState<DryRunRubric | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (pitch.length < 20) {
      setError("Pitch must be at least 20 characters.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const result = await postDryRun(opportunityId, pitch, {
        repoUrl: repoUrl || undefined,
        useLlm: false,
      });
      setRubric(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <form onSubmit={handleSubmit} className="mb-10 space-y-4">
        <div>
          <label htmlFor="pitch" className="mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Your pitch (1-3 paragraphs)
          </label>
          <textarea
            id="pitch"
            rows={6}
            value={pitch}
            onChange={(e) => setPitch(e.target.value)}
            placeholder="We're building a real-time pothole detector that runs on a Raspberry Pi..."
            className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
          />
        </div>
        <div>
          <label htmlFor="repo" className="mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Project repo URL (optional)
          </label>
          <input
            id="repo"
            type="url"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            placeholder="https://github.com/you/your-project"
            className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
          />
        </div>
        {error && (
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        )}
        <button
          type="submit"
          disabled={loading}
          className="rounded-full bg-indigo-600 px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-500 disabled:opacity-50"
        >
          {loading ? "Judging..." : "Submit pitch"}
        </button>
      </form>

      {rubric && <Scorecard rubric={rubric} />}
    </div>
  );
}

function Scorecard({ rubric }: { rubric: DryRunRubric }) {
  const personaColors: Record<JudgePersona, string> = {
    industry: "border-blue-500 bg-blue-50 dark:bg-blue-950",
    academic: "border-purple-500 bg-purple-50 dark:bg-purple-950",
    vc: "border-emerald-500 bg-emerald-50 dark:bg-emerald-950",
  };

  return (
    <div>
      <div className="mb-6 rounded-lg border border-zinc-200 bg-white p-5 text-center dark:border-zinc-800 dark:bg-zinc-900">
        <p className="text-xs font-semibold tracking-wider text-zinc-500 uppercase">Overall</p>
        <p className="mt-1 text-4xl font-bold text-zinc-900 dark:text-zinc-50">
          {rubric.overall_score}<span className="text-lg text-zinc-400">/100</span>
        </p>
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
          {rubric.overall_feedback}
        </p>
        <p className="mt-1 text-xs text-zinc-400">
          scored by {rubric.rubric_source === "llm" ? "LLM judges" : "heuristic fallback"}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {rubric.scores.map((s) => (
          <JudgeCard key={s.judge} score={s} borderClass={personaColors[s.judge]} />
        ))}
      </div>
    </div>
  );
}

function JudgeCard({ score, borderClass }: { score: JudgeScore; borderClass: string }) {
  const dims = [
    { label: "Feasibility", value: score.rubric.feasibility },
    { label: "Novelty", value: score.rubric.novelty },
    { label: "Market fit", value: score.rubric.market_fit },
    { label: "Polish", value: score.rubric.polish },
  ];

  return (
    <div className={`rounded-lg border-l-4 p-4 ${borderClass}`}>
      <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">
        {score.judge_name}
      </p>
      <p className="mt-1 text-2xl font-bold text-zinc-900 dark:text-zinc-50">
        {score.score}<span className="text-sm text-zinc-400">/100</span>
      </p>
      <div className="mt-3 space-y-1">
        {dims.map((d) => (
          <div key={d.label} className="flex items-center justify-between text-xs">
            <span className="text-zinc-500 dark:text-zinc-400">{d.label}</span>
            <div className="flex items-center gap-2">
              <div className="h-1.5 w-16 rounded-full bg-zinc-200 dark:bg-zinc-700">
                <div
                  className="h-1.5 rounded-full bg-indigo-500"
                  style={{ width: `${(d.value / 25) * 100}%` }}
                />
              </div>
              <span className="w-6 text-right font-medium text-zinc-700 dark:text-zinc-300">
                {d.value}
              </span>
            </div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-zinc-600 dark:text-zinc-400">{score.feedback}</p>
    </div>
  );
}
