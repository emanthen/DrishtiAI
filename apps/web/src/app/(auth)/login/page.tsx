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
  const [totpCode, setTotpCode] = useState("");
  const [showTotp, setShowTotp] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const tokens = await api.auth.login(email, password, showTotp ? totpCode : undefined);
      setTokens(tokens.access_token, tokens.refresh_token);
      const user = await api.auth.me(tokens.access_token);
      setUser(user);
      router.push("/");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Login failed";
      setError(msg);
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

          {/* TOTP field — shown when user toggles or after an auth failure hint */}
          {showTotp ? (
            <div>
              <label className="block text-xs font-medium text-steel mb-1" htmlFor="totp">
                Authenticator code
              </label>
              <input
                id="totp"
                type="text"
                inputMode="numeric"
                pattern="\d{6}"
                maxLength={6}
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ""))}
                placeholder="000000"
                className="w-full rounded-[4px] border border-hairline bg-white dark:bg-ink dark:border-hairline-dark px-3 py-2 text-sm font-mono text-ink dark:text-bone tracking-widest focus:outline-none focus:ring-1 focus:ring-signal"
                autoComplete="one-time-code"
              />
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setShowTotp(true)}
              className="text-xs text-steel hover:text-ink dark:hover:text-bone transition-colors"
            >
              Using an authenticator? Enter code
            </button>
          )}

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
