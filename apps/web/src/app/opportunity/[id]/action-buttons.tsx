"use client";

import { useState } from "react";
import { postScaffold } from "@/lib/api-client";
import type { ScaffoldResult } from "@/types/scaffold";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function ScaffoldButton({ opportunityId }: { opportunityId: string }) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ScaffoldResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"dry" | "github">("dry");

  async function handleScaffold() {
    setLoading(true);
    setError(null);
    try {
      const res = await postScaffold(opportunityId, {
        dryRun: mode === "dry",
        useLlm: true,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scaffold failed");
    } finally {
      setLoading(false);
    }
  }

  if (result) {
    return (
      <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-5 dark:border-emerald-800 dark:bg-emerald-950">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-emerald-600 dark:text-emerald-400 text-lg">&#10003;</span>
          <h3 className="font-semibold text-emerald-900 dark:text-emerald-100">
            Starter repo ready &mdash; {result.template}
          </h3>
        </div>

        {/* Link to created GitHub repo */}
        {result.repo_url ? (
          <a
            href={result.repo_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mb-3 inline-flex items-center gap-2 rounded-full bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-emerald-500"
          >
            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 16 16"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
            Open repo on GitHub
          </a>
        ) : (
          <div className="mb-3 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
            Preview mode &mdash; repo not created on GitHub.
            <button
              onClick={() => { setMode("github"); setResult(null); }}
              className="ml-2 font-medium text-amber-900 underline hover:no-underline dark:text-amber-100"
            >
              Create it for real
            </button>
          </div>
        )}

        <div className="text-sm text-emerald-800 dark:text-emerald-200 mb-3">
          {result.files.length} files &middot; Template: {result.template} &middot; Brief: {result.brief_source}
        </div>

        <details>
          <summary className="cursor-pointer text-sm font-medium text-emerald-700 dark:text-emerald-300">
            View BRIEF.md
          </summary>
          <pre className="mt-3 max-h-96 overflow-auto rounded bg-zinc-900 p-4 text-xs text-zinc-100 whitespace-pre-wrap">
            {result.brief_markdown}
          </pre>
        </details>

        <details className="mt-2">
          <summary className="cursor-pointer text-sm font-medium text-emerald-700 dark:text-emerald-300">
            File list ({result.files.length})
          </summary>
          <ul className="mt-2 text-xs text-emerald-600 dark:text-emerald-400 space-y-0.5">
            {result.files.map((f) => (
              <li key={f.path}>{f.path} ({f.bytes} bytes)</li>
            ))}
          </ul>
        </details>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={handleScaffold}
        disabled={loading}
        className="rounded-full bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:opacity-50"
      >
        {loading ? "Generating..." : mode === "github" ? "Create repo on GitHub" : "Preview starter repo"}
      </button>
      {mode === "dry" && (
        <button
          onClick={() => setMode("github")}
          className="text-sm text-emerald-600 hover:underline dark:text-emerald-400"
        >
          or create on GitHub directly
        </button>
      )}
      {mode === "github" && (
        <button
          onClick={() => setMode("dry")}
          className="text-sm text-zinc-500 hover:underline"
        >
          just preview
        </button>
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}

export function RegisterButton({ opportunityId }: { opportunityId: string }) {
  const [registered, setRegistered] = useState(false);
  const [loading, setLoading] = useState(false);

  async function toggle() {
    setLoading(true);
    try {
      const method = registered ? "DELETE" : "POST";
      const res = await fetch(
        `${API_BASE_URL}/opportunities/${encodeURIComponent(opportunityId)}/register`,
        { method, credentials: "include", headers: { Accept: "application/json" } }
      );
      if (res.ok) setRegistered(!registered);
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      onClick={toggle}
      disabled={loading}
      className={`rounded-full px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50 ${
        registered
          ? "bg-emerald-100 text-emerald-700 hover:bg-emerald-200 dark:bg-emerald-900 dark:text-emerald-200"
          : "bg-amber-500 text-white hover:bg-amber-400"
      }`}
    >
      {loading ? "..." : registered ? "Registered \u2713" : "Register interest"}
    </button>
  );
}
