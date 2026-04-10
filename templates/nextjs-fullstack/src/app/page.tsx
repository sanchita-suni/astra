export default function Home() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-50 p-8">
      <div className="max-w-xl text-center">
        <p className="mb-2 text-sm font-semibold tracking-wider text-indigo-600 uppercase">
          Astra starter
        </p>
        <h1 className="text-4xl font-bold tracking-tight text-zinc-900">
          Hello, hackathon.
        </h1>
        <p className="mt-4 text-zinc-600">
          Edit <code className="rounded bg-zinc-200 px-1">src/app/page.tsx</code>{" "}
          to start building. Read <code className="rounded bg-zinc-200 px-1">BRIEF.md</code>{" "}
          for what you&apos;re building.
        </p>
      </div>
    </main>
  );
}
