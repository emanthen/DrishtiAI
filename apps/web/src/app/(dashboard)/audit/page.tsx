"use client";

import { useEffect, useState, useCallback } from "react";
import { useAuthStore } from "@/store/auth";
import { API_BASE } from "@/lib/api";

interface AuditEntry {
  id: string;
  actor_user_id: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  ts: string;
  ip: string | null;
  meta_json: Record<string, unknown> | null;
}

interface AuditPage {
  items: AuditEntry[];
  next_cursor: string | null;
}

const ACTION_STYLES: Record<string, string> = {
  "user.login_success":  "bg-confirm/15 text-confirm",
  "user.login_failed":   "bg-alert/15 text-alert",
  "user.logout":         "bg-steel/15 text-steel",
  "user.create":         "bg-signal/15 text-signal",
  "user.update":         "bg-signal/10 text-signal",
  "user.activate":       "bg-confirm/15 text-confirm",
  "user.deactivate":     "bg-alert/10 text-alert",
  "user.reset_password": "bg-steel/10 text-steel",
};

function actionBadge(action: string) {
  const cls = ACTION_STYLES[action] ?? "bg-steel/10 text-steel";
  return (
    <span className={`inline-block text-xs font-mono px-1.5 py-0.5 rounded ${cls}`}>
      {action}
    </span>
  );
}

function fmt(ts: string) {
  return new Date(ts).toLocaleString("en-GB", {
    year: "numeric", month: "short", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

export default function AuditPage() {
  const { accessToken } = useAuthStore();
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);

  // Filters
  const [filterAction, setFilterAction] = useState("");
  const [filterActor, setFilterActor] = useState("");
  const [filterTarget, setFilterTarget] = useState("");

  const load = useCallback(async (nextCursor?: string | null) => {
    if (!accessToken) return;
    setLoading(true);
    const params = new URLSearchParams({ limit: "100" });
    if (filterAction)  params.set("action",         filterAction);
    if (filterActor)   params.set("actor_user_id",   filterActor);
    if (filterTarget)  params.set("target_id",       filterTarget);
    if (nextCursor)    params.set("cursor",           nextCursor);
    try {
      const res = await fetch(`${API_BASE}/audit-logs?${params}`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!res.ok) throw new Error(await res.text());
      const data: AuditPage = await res.json();
      if (nextCursor) {
        setEntries((prev) => [...prev, ...data.items]);
      } else {
        setEntries(data.items);
      }
      setCursor(data.next_cursor);
      setHasMore(data.next_cursor !== null);
    } finally {
      setLoading(false);
    }
  }, [accessToken, filterAction, filterActor, filterTarget]);

  useEffect(() => { load(); }, [load]);

  function applyFilters(e: React.FormEvent) {
    e.preventDefault();
    setCursor(null);
    load(null);
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-ink dark:text-bone">Audit log</h1>
        <p className="text-sm text-steel mt-0.5">Immutable record of security-relevant actions.</p>
      </div>

      {/* Filters */}
      <form onSubmit={applyFilters} className="flex flex-wrap gap-3 mb-5 items-end">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-steel">Action</span>
          <input
            value={filterAction} onChange={(e) => setFilterAction(e.target.value)}
            className="input-base text-sm w-44" placeholder="user.login…"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-steel">Actor user ID</span>
          <input
            value={filterActor} onChange={(e) => setFilterActor(e.target.value)}
            className="input-base text-sm font-mono w-72" placeholder="uuid"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-steel">Target ID</span>
          <input
            value={filterTarget} onChange={(e) => setFilterTarget(e.target.value)}
            className="input-base text-sm font-mono w-72" placeholder="uuid or email"
          />
        </label>
        <button type="submit" className="px-3 py-1.5 text-sm bg-signal text-white rounded hover:bg-signal/90">
          Filter
        </button>
        <button
          type="button"
          onClick={() => { setFilterAction(""); setFilterActor(""); setFilterTarget(""); }}
          className="px-3 py-1.5 text-sm border border-hairline dark:border-hairline-dark rounded text-steel hover:text-ink dark:hover:text-bone"
        >
          Clear
        </button>
      </form>

      {loading && entries.length === 0 ? (
        <p className="text-sm text-steel">Loading…</p>
      ) : entries.length === 0 ? (
        <p className="text-sm text-steel">No audit entries found.</p>
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-hairline dark:border-hairline-dark">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-hairline dark:border-hairline-dark bg-bone/50 dark:bg-ink/50">
                  <th className="text-left px-4 py-2 text-xs font-semibold text-steel uppercase tracking-wide">Time</th>
                  <th className="text-left px-4 py-2 text-xs font-semibold text-steel uppercase tracking-wide">Action</th>
                  <th className="text-left px-4 py-2 text-xs font-semibold text-steel uppercase tracking-wide">Actor</th>
                  <th className="text-left px-4 py-2 text-xs font-semibold text-steel uppercase tracking-wide">Target</th>
                  <th className="text-left px-4 py-2 text-xs font-semibold text-steel uppercase tracking-wide">IP</th>
                  <th className="text-left px-4 py-2 text-xs font-semibold text-steel uppercase tracking-wide">Meta</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e, i) => (
                  <tr
                    key={e.id}
                    className={`border-b border-hairline dark:border-hairline-dark last:border-0 ${i % 2 === 1 ? "bg-bone/20 dark:bg-ink/20" : ""}`}
                  >
                    <td className="px-4 py-2 whitespace-nowrap text-xs font-mono text-steel">{fmt(e.ts)}</td>
                    <td className="px-4 py-2 whitespace-nowrap">{actionBadge(e.action)}</td>
                    <td className="px-4 py-2 whitespace-nowrap text-xs font-mono text-steel truncate max-w-[180px]" title={e.actor_user_id ?? ""}>
                      {e.actor_user_id ? e.actor_user_id.slice(0, 8) + "…" : "—"}
                    </td>
                    <td className="px-4 py-2 text-xs text-steel">
                      {e.target_type && <span className="text-ink dark:text-bone mr-1">{e.target_type}</span>}
                      {e.target_id && <span className="font-mono">{e.target_id.length > 24 ? e.target_id.slice(0, 24) + "…" : e.target_id}</span>}
                      {!e.target_type && !e.target_id && "—"}
                    </td>
                    <td className="px-4 py-2 text-xs font-mono text-steel whitespace-nowrap">{e.ip ?? "—"}</td>
                    <td className="px-4 py-2 text-xs font-mono text-steel max-w-[200px] truncate" title={e.meta_json ? JSON.stringify(e.meta_json) : ""}>
                      {e.meta_json ? JSON.stringify(e.meta_json) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {hasMore && (
            <button
              onClick={() => load(cursor)}
              disabled={loading}
              className="mt-4 px-4 py-1.5 text-sm border border-hairline dark:border-hairline-dark rounded text-steel hover:text-ink dark:hover:text-bone disabled:opacity-50"
            >
              {loading ? "Loading…" : "Load more"}
            </button>
          )}
        </>
      )}
    </div>
  );
}
