"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const { accessToken, setTokens, setUser } = useAuthStore();
  const [email, setEmail] = useState("admin@drishtiai.local");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (accessToken) router.replace("/");
  }, [accessToken, router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const tokens = await api.auth.login(email, password);
      setTokens(tokens.access_token, tokens.refresh_token);
      const me = await api.auth.me(tokens.access_token);
      setUser(me);
      router.replace("/");
    } catch {
      setError("Invalid email or password.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-bone dark:bg-ink flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-xl font-semibold text-ink dark:text-bone">DrishtiAI</h1>
          <p className="mt-1 text-xs text-steel">ANPR Platform</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-[12px] border border-hairline dark:border-hairline-dark bg-white dark:bg-ink/60 p-6 space-y-4"
        >
          <div className="space-y-1">
            <label className="block text-xs font-medium text-steel">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
              className="w-full rounded-[4px] border border-hairline dark:border-hairline-dark bg-white dark:bg-ink px-3 py-2 text-sm text-ink dark:text-bone focus:outline-none focus:ring-1 focus:ring-signal"
            />
          </div>

          <div className="space-y-1">
            <label className="block text-xs font-medium text-steel">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full rounded-[4px] border border-hairline dark:border-hairline-dark bg-white dark:bg-ink px-3 py-2 text-sm text-ink dark:text-bone focus:outline-none focus:ring-1 focus:ring-signal"
            />
          </div>

          {error && <p className="text-xs text-alert">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-[4px] bg-signal text-white py-2 text-sm font-medium hover:bg-signal/90 transition-colors disabled:opacity-50"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="mt-4 text-center text-[11px] text-steel">
          Demo:{" "}
          <span className="font-mono">admin@drishtiai.local</span>
          {" / "}
          <span className="font-mono">devpassword123</span>
        </p>
      </div>
    </div>
  );
}
