import { notFound } from "next/navigation";

import { AstraApiError, getOpportunity } from "@/lib/api-client";
import type { Opportunity } from "@/types/opportunity";

import RehearsalForm from "./rehearsal-form";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function RehearsalPage({ params }: PageProps) {
  const { id } = await params;

  let opp: Opportunity;
  try {
    opp = await getOpportunity(id);
  } catch (err) {
    if (err instanceof AstraApiError && err.status === 404) {
      notFound();
    }
    throw err;
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      <main className="mx-auto max-w-4xl px-6 py-16">
        <header className="mb-10">
          <p className="mb-2 text-sm font-medium tracking-wider text-indigo-600 uppercase dark:text-indigo-400">
            Dry-Run Demo Day
          </p>
          <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50 sm:text-4xl">
            {opp.metadata.title}
          </h1>
          <p className="mt-2 text-zinc-600 dark:text-zinc-400">
            Pitch your project. Three AI judges will score it on feasibility,
            novelty, market fit, and polish.
          </p>
        </header>

        <RehearsalForm opportunityId={id} />
      </main>
    </div>
  );
}
