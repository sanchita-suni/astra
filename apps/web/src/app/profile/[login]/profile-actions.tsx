"use client";

import { useEffect, useState } from "react";
import { getMe, uploadResume } from "@/lib/api-client";
import type { UserProfile, ResumeSkills } from "@/types/user";

export default function ProfileActions({ login }: { login: string }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [uploading, setUploading] = useState(false);
  const [resumeResult, setResumeResult] = useState<ResumeSkills | null>(null);

  useEffect(() => {
    getMe().then(setUser);
  }, []);

  // Only show actions if this is the logged-in user's profile
  if (!user || user.github_login !== login) return null;

  async function handleResume(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const result = await uploadResume(file);
      setResumeResult(result);
    } catch {
      // ignore
    } finally {
      setUploading(false);
    }
  }

  const resume = resumeResult || user.resume;
  const questionnaire = user.questionnaire;

  return (
    <div className="mb-10 space-y-6">
      {/* Resume */}
      <section>
        <h2 className="mb-4 text-sm font-semibold tracking-wider text-zinc-500 uppercase">
          Resume skills
        </h2>
        {resume ? (
          <div className="rounded-lg border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
            <div className="flex flex-wrap gap-2 mb-3">
              {resume.skills.map((s) => (
                <span key={s} className="rounded-full bg-purple-100 px-3 py-1 text-xs font-medium text-purple-800 dark:bg-purple-900 dark:text-purple-200">
                  {s}
                </span>
              ))}
            </div>
            {resume.education.length > 0 && (
              <div className="mb-2">
                <p className="text-xs font-medium text-zinc-500 mb-1">Education</p>
                {resume.education.map((e, i) => (
                  <p key={i} className="text-sm text-zinc-700 dark:text-zinc-300">{e}</p>
                ))}
              </div>
            )}
            {resume.experience_summary && (
              <p className="text-sm text-zinc-600 dark:text-zinc-400">{resume.experience_summary}</p>
            )}
            <p className="mt-2 text-xs text-zinc-400">Extracted via: {resume.extraction_source}</p>
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-zinc-300 bg-white p-5 text-center dark:border-zinc-700 dark:bg-zinc-900">
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-3">
              Upload your resume to extract skills automatically
            </p>
            <label className="cursor-pointer rounded-full bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500">
              {uploading ? "Uploading..." : "Upload PDF resume"}
              <input type="file" accept=".pdf" onChange={handleResume} className="hidden" disabled={uploading} />
            </label>
          </div>
        )}
      </section>

      {/* Questionnaire */}
      {questionnaire && (
        <section>
          <h2 className="mb-4 text-sm font-semibold tracking-wider text-zinc-500 uppercase">
            Your preferences
          </h2>
          <div className="rounded-lg border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <dt className="text-xs font-medium text-zinc-500">Experience</dt>
                <dd className="mt-1 text-sm font-medium text-zinc-900 dark:text-zinc-50 capitalize">{questionnaire.experience_level}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-zinc-500">Hours/week</dt>
                <dd className="mt-1 text-sm font-medium text-zinc-900 dark:text-zinc-50">{questionnaire.hours_per_week}h</dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="text-xs font-medium text-zinc-500 mb-1">Preferred types</dt>
                <dd className="flex flex-wrap gap-1.5">
                  {questionnaire.preferred_types.map((t) => (
                    <span key={t} className="rounded-full bg-indigo-100 px-2.5 py-0.5 text-xs font-medium text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200">{t}</span>
                  ))}
                </dd>
              </div>
              {questionnaire.skills_to_learn.length > 0 && (
                <div className="sm:col-span-2">
                  <dt className="text-xs font-medium text-zinc-500 mb-1">Want to learn</dt>
                  <dd className="flex flex-wrap gap-1.5">
                    {questionnaire.skills_to_learn.map((s) => (
                      <span key={s} className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900 dark:text-amber-200">{s}</span>
                    ))}
                  </dd>
                </div>
              )}
            </dl>
            <a href="/onboarding" className="mt-4 inline-block text-sm text-indigo-600 hover:underline dark:text-indigo-400">
              Edit preferences
            </a>
          </div>
        </section>
      )}
    </div>
  );
}
