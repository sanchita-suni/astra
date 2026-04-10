const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function LoginPage() {
  return (
    <div className="flex min-h-[80vh] items-center justify-center bg-zinc-50 dark:bg-zinc-950">
      <div className="max-w-sm text-center">
        <p className="mb-2 text-sm font-medium tracking-wider text-indigo-600 uppercase dark:text-indigo-400">
          Astra
        </p>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          Sign in
        </h1>
        <p className="mt-3 text-zinc-600 dark:text-zinc-400">
          Connect your GitHub account to get personalized hackathon recommendations,
          skill gap analysis, and your Proof-of-Work Vault.
        </p>
        <a
          href={`${API_BASE_URL}/auth/github`}
          className="mt-6 inline-block rounded-full bg-zinc-900 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          Sign in with GitHub
        </a>
      </div>
    </div>
  );
}
