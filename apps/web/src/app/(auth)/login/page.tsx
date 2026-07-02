"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

export default function LoginPage() {
  const router = useRouter();
  const { setTokens, setUser } = useAuthStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const tokens = await api.auth.login(email, password);
      setTokens(tokens.access_token, tokens.refresh_token);
      const user = await api.auth.me(tokens.access_token);
      setUser(user);
      router.push("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-bone dark:bg-ink p-4">
      <div className="w-full max-w-sm">
        <div className="mb-8">
          <h1 className="text-2xl font-medium text-ink dark:text-bone">DrishtiAI</h1>
          <p className="mt-1 text-sm text-steel">Sign in to the control room</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-steel mb-1" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-[4px] border border-hairline bg-white dark:bg-ink dark:border-hairline-dark px-3 py-2 text-sm text-ink dark:text-bone focus:outline-none focus:ring-1 focus:ring-signal"
              autoComplete="email"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-steel mb-1" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-[4px] border border-hairline bg-white dark:bg-ink dark:border-hairline-dark px-3 py-2 text-sm text-ink dark:text-bone focus:outline-none focus:ring-1 focus:ring-signal"
              autoComplete="current-password"
            />
          </div>

          {error && (
            <p className="text-sm text-alert" role="alert">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-[8px] bg-signal px-4 py-2 text-sm font-medium text-white transition-opacity duration-[120ms] hover:opacity-90 disabled:opacity-50"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </main>
  );
}
