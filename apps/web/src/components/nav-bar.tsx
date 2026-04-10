"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getMe, logout } from "@/lib/api-client";
import type { UserProfile } from "@/types/user";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function NavBar() {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getMe().then(setUser).finally(() => setLoading(false));
  }, []);

  async function handleLogout() {
    await logout();
    setUser(null);
    window.location.href = "/";
  }

  return (
    <nav className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
        <Link href="/" className="text-lg font-bold text-indigo-600 dark:text-indigo-400">
          Astra
        </Link>
        <div className="flex items-center gap-4">
          {loading ? null : user ? (
            <>
              <Link
                href={`/profile/${user.github_login}`}
                className="flex items-center gap-2 text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-50"
              >
                {user.github_avatar_url && (
                  <img
                    src={user.github_avatar_url}
                    alt=""
                    className="h-6 w-6 rounded-full"
                  />
                )}
                {user.github_name || user.github_login}
              </Link>
              <button
                onClick={handleLogout}
                className="text-sm text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-50"
              >
                Log out
              </button>
            </>
          ) : (
            <a
              href={`${API_BASE_URL}/auth/github`}
              className="rounded-full bg-zinc-900 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
            >
              Sign in with GitHub
            </a>
          )}
        </div>
      </div>
    </nav>
  );
}
