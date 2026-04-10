"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { updateQuestionnaire, uploadResume } from "@/lib/api-client";
import type { HackathonType, TimeAvailability, ExperienceLevel } from "@/types/user";

const EXPERIENCE_OPTIONS: { value: ExperienceLevel; label: string }[] = [
  { value: "beginner", label: "Beginner — first few hackathons" },
  { value: "intermediate", label: "Intermediate — done 3-10 hackathons" },
  { value: "advanced", label: "Advanced — veteran hacker" },
];

const TYPE_OPTIONS: { value: HackathonType; label: string }[] = [
  { value: "ai-ml", label: "AI / Machine Learning" },
  { value: "web", label: "Web Development" },
  { value: "mobile", label: "Mobile Apps" },
  { value: "hardware", label: "Hardware / IoT" },
  { value: "blockchain", label: "Blockchain / Web3" },
  { value: "data", label: "Data Science" },
  { value: "social-impact", label: "Social Impact" },
  { value: "open", label: "Open / General" },
];

const TIME_OPTIONS: { value: TimeAvailability; label: string }[] = [
  { value: "5", label: "~5 hours/week" },
  { value: "10", label: "~10 hours/week" },
  { value: "15", label: "~15 hours/week" },
  { value: "20", label: "~20 hours/week" },
  { value: "30", label: "~30 hours/week" },
  { value: "40+", label: "40+ hours/week (full time)" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [experience, setExperience] = useState<ExperienceLevel>("beginner");
  const [preferredTypes, setPreferredTypes] = useState<HackathonType[]>([]);
  const [skillsToLearn, setSkillsToLearn] = useState("");
  const [hoursPerWeek, setHoursPerWeek] = useState<TimeAvailability>("10");
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleType(t: HackathonType) {
    setPreferredTypes((prev) =>
      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]
    );
  }

  async function handleSubmit() {
    setLoading(true);
    setError(null);
    try {
      // Save questionnaire
      await updateQuestionnaire({
        experience_level: experience,
        preferred_types: preferredTypes,
        skills_to_learn: skillsToLearn
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        hours_per_week: hoursPerWeek,
      });

      // Upload resume if provided
      if (resumeFile) {
        await uploadResume(resumeFile);
      }

      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-[80vh] bg-zinc-50 dark:bg-zinc-950">
      <main className="mx-auto max-w-lg px-6 py-16">
        <p className="mb-2 text-sm font-medium tracking-wider text-indigo-600 uppercase dark:text-indigo-400">
          Welcome to Astra
        </p>
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
          Let&apos;s personalize your feed
        </h1>
        <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
          Step {step + 1} of 3
        </p>

        <div className="mt-8 space-y-6">
          {step === 0 && (
            <div className="space-y-4">
              <h2 className="font-medium text-zinc-900 dark:text-zinc-50">
                Your experience level
              </h2>
              {EXPERIENCE_OPTIONS.map((opt) => (
                <label
                  key={opt.value}
                  className={`flex cursor-pointer items-center gap-3 rounded-lg border p-4 transition-colors ${
                    experience === opt.value
                      ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950"
                      : "border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900"
                  }`}
                >
                  <input
                    type="radio"
                    name="experience"
                    checked={experience === opt.value}
                    onChange={() => setExperience(opt.value)}
                    className="accent-indigo-600"
                  />
                  <span className="text-sm text-zinc-700 dark:text-zinc-300">{opt.label}</span>
                </label>
              ))}
              <button
                onClick={() => setStep(1)}
                className="mt-4 rounded-full bg-indigo-600 px-6 py-2 text-sm font-medium text-white hover:bg-indigo-500"
              >
                Next
              </button>
            </div>
          )}

          {step === 1 && (
            <div className="space-y-4">
              <h2 className="font-medium text-zinc-900 dark:text-zinc-50">
                What kind of hackathons interest you?
              </h2>
              <div className="grid grid-cols-2 gap-2">
                {TYPE_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => toggleType(opt.value)}
                    className={`rounded-lg border px-3 py-2 text-sm transition-colors ${
                      preferredTypes.includes(opt.value)
                        ? "border-indigo-500 bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300"
                        : "border-zinc-200 text-zinc-700 dark:border-zinc-800 dark:text-zinc-300"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  Skills you want to learn (comma-separated)
                </label>
                <input
                  type="text"
                  value={skillsToLearn}
                  onChange={(e) => setSkillsToLearn(e.target.value)}
                  placeholder="e.g. PyTorch, React Native, Rust"
                  className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  Weekly time availability
                </label>
                <select
                  value={hoursPerWeek}
                  onChange={(e) => setHoursPerWeek(e.target.value as TimeAvailability)}
                  className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
                >
                  {TIME_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
              <div className="flex gap-3">
                <button onClick={() => setStep(0)} className="rounded-full border border-zinc-300 px-6 py-2 text-sm dark:border-zinc-700 dark:text-zinc-300">Back</button>
                <button onClick={() => setStep(2)} className="rounded-full bg-indigo-600 px-6 py-2 text-sm font-medium text-white hover:bg-indigo-500">Next</button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <h2 className="font-medium text-zinc-900 dark:text-zinc-50">
                Upload your resume (optional)
              </h2>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">
                We&apos;ll extract skills from your resume to improve matching. PDF only, max 5MB.
              </p>
              <input
                type="file"
                accept=".pdf"
                onChange={(e) => setResumeFile(e.target.files?.[0] ?? null)}
                className="block w-full text-sm text-zinc-500 file:mr-4 file:rounded-full file:border-0 file:bg-indigo-50 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-indigo-700 hover:file:bg-indigo-100 dark:text-zinc-400 dark:file:bg-indigo-950 dark:file:text-indigo-300"
              />
              {resumeFile && (
                <p className="text-sm text-emerald-600 dark:text-emerald-400">
                  Selected: {resumeFile.name}
                </p>
              )}
              {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
              <div className="flex gap-3">
                <button onClick={() => setStep(1)} className="rounded-full border border-zinc-300 px-6 py-2 text-sm dark:border-zinc-700 dark:text-zinc-300">Back</button>
                <button
                  onClick={handleSubmit}
                  disabled={loading}
                  className="rounded-full bg-indigo-600 px-6 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
                >
                  {loading ? "Saving..." : resumeFile ? "Save & Upload" : "Save & Skip Resume"}
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
