"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/store/auth";
import { api, Watchlist, WatchlistEntry } from "@/lib/api";

const CATEGORY_STYLES: Record<string, string> = {
  blocked:       "bg-alert/15 text-alert",
  vip:           "bg-signal/15 text-signal",
  resident:      "bg-confirm/15 text-confirm",
  vendor:        "bg-steel/15 text-steel",
  staff:         "bg-steel/15 text-steel",
  police_notice: "bg-alert/25 text-alert font-semibold",
};

export default function WatchlistsPage() {
  const { accessToken } = useAuthStore();
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [selected, setSelected] = useState<Watchlist | null>(null);
  const [entries, setEntries] = useState<WatchlistEntry[]>([]);
  const [loading, setLoading] = useState(true);

  // New watchlist form
  const [showCreate, setShowCreate] = useState(false);
  const [wlName, setWlName] = useState("");
  const [wlCategory, setWlCategory] = useState<Watchlist["category"]>("blocked");
  const [wlSiteId, setWlSiteId] = useState("");

  // New entry form
  const [entryText, setEntryText] = useState("");
  const [entryPattern, setEntryPattern] = useState<"exact" | "prefix" | "fuzzy">("exact");
  const [entryNotes, setEntryNotes] = useState("");

  useEffect(() => {
    if (!accessToken) return;
    api.watchlists.list(accessToken).then((wls) => {
      setWatchlists(wls);
      if (wls.length > 0 && !selected) setSelected(wls[0]);
      setLoading(false);
    });
  }, [accessToken]);

  useEffect(() => {
    if (!accessToken || !selected) return;
    api.watchlists.listEntries(accessToken, selected.id).then(setEntries);
  }, [accessToken, selected]);

  async function createWatchlist() {
    if (!accessToken || !wlName.trim() || !wlSiteId.trim()) return;
    const wl = await api.watchlists.create(accessToken, {
      site_id: wlSiteId,
      name: wlName,
      category: wlCategory,
    });
    setWatchlists((prev) => [...prev, wl]);
    setSelected(wl);
    setShowCreate(false);
    setWlName("");
  }

  async function deleteWatchlist(id: string) {
    if (!accessToken) return;
    await api.watchlists.delete(accessToken, id);
    const remaining = watchlists.filter((w) => w.id !== id);
    setWatchlists(remaining);
    setSelected(remaining[0] ?? null);
  }

  async function addEntry() {
    if (!accessToken || !selected || !entryText.trim()) return;
    const entry = await api.watchlists.addEntry(accessToken, selected.id, {
      plate_text: entryText.toUpperCase().trim(),
      plate_pattern: entryPattern,
      notes: entryNotes || undefined,
    });
    setEntries((prev) => [...prev, entry]);
    setEntryText("");
    setEntryNotes("");
  }

  async function removeEntry(entryId: string) {
    if (!accessToken || !selected) return;
    await api.watchlists.removeEntry(accessToken, selected.id, entryId);
    setEntries((prev) => prev.filter((e) => e.id !== entryId));
  }

  if (loading) return <p className="p-6 text-sm text-steel">Loading…</p>;

  return (
    <div className="flex h-full min-h-screen">
      {/* Watchlist list */}
      <aside className="w-56 shrink-0 border-r border-hairline dark:border-hairline-dark p-3 space-y-1">
        <div className="flex items-center justify-between mb-2 px-1">
          <span className="text-xs font-medium text-steel uppercase tracking-wider">Watchlists</span>
          <button
            onClick={() => setShowCreate(true)}
            className="text-xs text-signal hover:text-signal/70"
          >
            + New
          </button>
        </div>

        {watchlists.map((wl) => (
          <button
            key={wl.id}
            onClick={() => setSelected(wl)}
            className={`w-full text-left px-2 py-2 rounded text-sm transition-colors ${
              selected?.id === wl.id
                ? "bg-signal/10 text-ink dark:text-bone"
                : "text-steel hover:text-ink dark:hover:text-bone"
            }`}
          >
            <span className="block truncate">{wl.name}</span>
            <span className={`inline-block mt-0.5 px-1.5 py-0 rounded text-[10px] ${CATEGORY_STYLES[wl.category] ?? ""}`}>
              {wl.category}
            </span>
          </button>
        ))}

        {watchlists.length === 0 && (
          <p className="text-xs text-steel px-1 py-4 text-center">No watchlists yet.</p>
        )}
      </aside>

      {/* Main panel */}
      <main className="flex-1 p-6">
        {showCreate && (
          <div className="mb-6 p-4 rounded-lg border border-hairline dark:border-hairline-dark bg-white dark:bg-ink/40 max-w-md">
            <h2 className="text-sm font-medium mb-3 text-ink dark:text-bone">New Watchlist</h2>
            <div className="space-y-2">
              <input
                className="w-full input-field text-sm"
                placeholder="Name (e.g. Blocked vehicles)"
                value={wlName}
                onChange={(e) => setWlName(e.target.value)}
              />
              <input
                className="w-full input-field text-sm"
                placeholder="Site ID (UUID)"
                value={wlSiteId}
                onChange={(e) => setWlSiteId(e.target.value)}
              />
              <select
                className="w-full input-field text-sm"
                value={wlCategory}
                onChange={(e) => setWlCategory(e.target.value as Watchlist["category"])}
              >
                {(["blocked","vip","resident","vendor","staff","police_notice"] as const).map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
              <div className="flex gap-2">
                <button onClick={createWatchlist} className="btn-primary text-sm px-3 py-1.5">Create</button>
                <button onClick={() => setShowCreate(false)} className="btn-ghost text-sm px-3 py-1.5">Cancel</button>
              </div>
            </div>
          </div>
        )}

        {selected ? (
          <>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h1 className="text-lg font-medium text-ink dark:text-bone">{selected.name}</h1>
                <span className={`inline-block px-2 py-0.5 rounded text-xs mt-0.5 ${CATEGORY_STYLES[selected.category]}`}>
                  {selected.category}
                </span>
              </div>
              <button
                onClick={() => deleteWatchlist(selected.id)}
                className="text-xs text-alert hover:text-alert/70 transition-colors"
              >
                Delete watchlist
              </button>
            </div>

            {/* Entry form */}
            <div className="flex gap-2 mb-4 flex-wrap">
              <input
                className="input-field text-sm w-36"
                placeholder="Plate text"
                value={entryText}
                onChange={(e) => setEntryText(e.target.value.toUpperCase())}
                onKeyDown={(e) => e.key === "Enter" && addEntry()}
              />
              <select
                className="input-field text-sm"
                value={entryPattern}
                onChange={(e) => setEntryPattern(e.target.value as typeof entryPattern)}
              >
                <option value="exact">Exact</option>
                <option value="prefix">Prefix</option>
                <option value="fuzzy">Fuzzy</option>
              </select>
              <input
                className="input-field text-sm flex-1 min-w-[120px]"
                placeholder="Notes (optional)"
                value={entryNotes}
                onChange={(e) => setEntryNotes(e.target.value)}
              />
              <button onClick={addEntry} className="btn-primary text-sm px-3 py-1.5 shrink-0">
                Add entry
              </button>
            </div>

            {/* Entry list */}
            {entries.length === 0 ? (
              <p className="text-sm text-steel">No entries. Add a plate above.</p>
            ) : (
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="text-left text-xs text-steel border-b border-hairline dark:border-hairline-dark">
                    <th className="pb-2 pr-4 font-medium">Plate</th>
                    <th className="pb-2 pr-4 font-medium">Pattern</th>
                    <th className="pb-2 font-medium">Notes</th>
                    <th className="pb-2" />
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry) => (
                    <tr
                      key={entry.id}
                      className="border-b border-hairline dark:border-hairline-dark hover:bg-hairline/30 dark:hover:bg-hairline-dark/30"
                    >
                      <td className="py-2 pr-4">
                        <span className="font-mono text-ink dark:text-bone tracking-widest">
                          {entry.plate_text}
                        </span>
                      </td>
                      <td className="py-2 pr-4 text-steel text-xs">{entry.plate_pattern}</td>
                      <td className="py-2 text-steel text-xs">{entry.notes ?? "—"}</td>
                      <td className="py-2 text-right">
                        <button
                          onClick={() => removeEntry(entry.id)}
                          className="text-xs text-alert hover:text-alert/70 transition-colors"
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        ) : (
          <div className="text-center py-20 text-steel text-sm">
            Select a watchlist or create one to get started.
          </div>
        )}
      </main>
    </div>
  );
}
