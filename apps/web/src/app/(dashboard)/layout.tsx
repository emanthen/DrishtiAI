"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/store/auth";
import { api, API_BASE } from "@/lib/api";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { accessToken, user, logout } = useAuthStore();
  const [offlineCount, setOfflineCount] = useState(0);

  useEffect(() => {
    if (!accessToken) {
      router.replace("/login");
      return;
    }
    async function checkHealth() {
      try {
        const res = await fetch(`${API_BASE}/cameras/health-summary`, {
          headers: { Authorization: `Bearer ${accessToken}` },
        });
        if (res.ok) {
          const data = await res.json();
          setOfflineCount(data.offline ?? 0);
        }
      } catch {}
    }
    checkHealth();
    const id = setInterval(checkHealth, 30_000);
    return () => clearInterval(id);
  }, [accessToken, router]);

  async function handleLogout() {
    if (accessToken) {
      try {
        await api.auth.logout(accessToken);
      } catch {}
    }
    logout();
    router.replace("/login");
  }

  if (!accessToken) return null;

  return (
    <div className="flex min-h-screen bg-bone dark:bg-ink">
      {/* Sidebar */}
      <nav className="w-56 shrink-0 border-r border-hairline dark:border-hairline-dark flex flex-col">
        <div className="px-4 py-4 border-b border-hairline dark:border-hairline-dark">
          <span className="text-base font-medium text-ink dark:text-bone">DrishtiAI</span>
        </div>

        <div className="flex-1 py-2">
          <NavItem href="/" label="Live view" />
          <NavItem href="/analytics" label="Analytics" />
          <NavItem href="/events" label="Events" />
          <NavItem href="/alerts" label="Alerts" />
          <NavItem href="/cameras" label="Cameras" />
          <NavItem href="/watchlists" label="Watchlists" />
          <NavItem href="/parking" label="Parking" />
          <NavItem href="/gates" label="Gates" />
          <NavItem href="/visitor-passes" label="Visitor passes" />
          <NavItem href="/users" label="Users" />
          <NavItem href="/webhooks" label="Webhooks" />
          <NavItem href="/reports" label="Reports" />
        </div>

        <div className="px-4 py-3 border-t border-hairline dark:border-hairline-dark">
          <p className="text-xs text-steel truncate">{user?.email}</p>
          <button
            onClick={handleLogout}
            className="mt-1 text-xs text-steel hover:text-ink dark:hover:text-bone transition-colors"
          >
            Sign out
          </button>
        </div>
      </nav>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        {offlineCount > 0 && (
          <div className="bg-alert/10 border-b border-alert/30 px-6 py-2 flex items-center gap-2">
            <span className="inline-flex rounded-full h-2 w-2 bg-alert" />
            <p className="text-xs font-semibold text-alert">
              {offlineCount} camera{offlineCount > 1 ? "s" : ""} offline —{" "}
              <Link href="/cameras" className="underline">view cameras</Link>
            </p>
          </div>
        )}
        {children}
      </main>
    </div>
  );
}

function NavItem({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="block px-4 py-2 text-sm text-steel hover:text-ink dark:hover:text-bone hover:bg-hairline dark:hover:bg-hairline-dark transition-colors"
    >
      {label}
    </Link>
  );
}
