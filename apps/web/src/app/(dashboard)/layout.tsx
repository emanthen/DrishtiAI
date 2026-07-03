"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/store/auth";
import { api } from "@/lib/api";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { accessToken, user, logout } = useAuthStore();

  useEffect(() => {
    if (!accessToken) {
      router.replace("/login");
    }
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
          <NavItem href="/events" label="Events" />
          <NavItem href="/alerts" label="Alerts" />
          <NavItem href="/cameras" label="Cameras" />
          <NavItem href="/watchlists" label="Watchlists" />
          <NavItem href="/parking" label="Parking" />
          <NavItem href="/gates" label="Gates" />
          <NavItem href="/visitor-passes" label="Visitor passes" />
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
      <main className="flex-1 overflow-auto">{children}</main>
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
