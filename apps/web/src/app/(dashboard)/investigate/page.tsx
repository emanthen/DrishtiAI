"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/auth";
import { api, API_BASE, type PlateSearchResult } from "@/lib/api";
import { formatTs, relativeTime } from "@/lib/utils";

const COLOR_HEX: Record<string, string> = {
  white: "#f5f5f5", black: "#1a1a1a", silver: "#c0c0c0", grey: "#808080",
  red: "#dc2626", blue: "#2563eb", green: "#16a34a", yellow: "#ca8a04",
  orange: "#ea580c", brown: "#92400e", maroon: "#881337", other: "#6b7280",
};

const KIND_STYLES: Record<string, { label: string; cls: string }> = {
  plate_read:    { label: "Plate read",    cls: "bg-confirm/15 text-confirm" },
  watchlist_hit: { label: "Watchlist hit", cls: "bg-alert/15 text-alert" },
  wrong_way:     { label: "Wrong way",     cls: "bg-alert/15 text-alert" },
  gate_open:     { label: "Gate open",     cls: "bg-signal/15 text-signal" },
};

function KindChip({ kind }: { kind: string }) {
  const cfg = KIND_STYLES[kind] ?? { label: kind, cls: "bg-steel/10 text-steel" };
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${cfg.cls}`}>
      {cfg.label}
    </span>
  );
}

export default function InvestigatePage() {
  const { accessToken } = useAuthStore();
  const [query, setQuery] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [selected, setSelected] = useState<PlateSearchResult | null>(null);
  const [activeTab, setActiveTab] = useState<"timeline" | "sightings">("timeline");

  function handleInput(val: string) {
    setQuery(val);
    if (!val) { setDebouncedQ(""); setSelected(null); return; }
    const t = setTimeout(() => setDebouncedQ(val), 350);
    return () => clearTimeout(t);
  }

  const { data: results = [], isFetching: searching } = useQuery({
    queryKey: ["plates-search", debouncedQ],
    queryFn: () => api.plates.search(accessToken!, debouncedQ),
    enabled: !!accessToken && debouncedQ.length >= 2,
    staleTime: 15_000,
  });

  const { data: timeline, isFetching: loadingTimeline } = useQuery({
    queryKey: ["plate-timeline", selected?.id],
    queryFn: () => api.plates.timeline(accessToken!, selected!.id, 30),
    enabled: !!accessToken && !!selected && activeTab === "timeline",
    staleTime: 20_000,
  });

  const { data: sightings = [], isFetching: loadingSightings } = useQuery({
    queryKey: ["plate-sightings", selected?.id],
    queryFn: () => api.plates.cameraSightings(accessToken!, selected!.id, 30),
    enabled: !!accessToken && !!selected && activeTab === "sightings",
    staleTime: 20_000,
  });

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Header + search */}
      <div>
        <h1 className="text-lg font-medium text-ink dark:text-bone mb-1">Investigate</h1>
        <p className="text-xs text-steel mb-4">Search any plate to see its full history and camera trail.</p>
        <div className="relative max-w-md">
          <input
            type="text"
            placeholder="Enter plate (partial ok, e.g. BA1PA)"
            value={query}
            onChange={(e) => handleInput(e.target.value)}
            className="w-full rounded-[6px] border border-hairline dark:border-hairline-dark bg-white dark:bg-ink px-4 py-2.5 text-sm text-ink dark:text-bone focus:outline-none focus:ring-2 focus:ring-signal font-mono"
            autoFocus
          />
          {query && (
            <button
              onClick={() => { setQuery(""); setDebouncedQ(""); setSelected(null); }}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-steel hover:text-ink dark:hover:text-bone transition-colors text-xs"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Search results */}
      {debouncedQ.length >= 2 && !selected && (
        <div>
          {searching && <p className="text-xs text-steel">Searching…</p>}
          {!searching && results.length === 0 && (
            <p className="text-sm text-steel">No plates matching "{debouncedQ}".</p>
          )}
          {results.length > 0 && (
            <div className="rounded-[12px] border border-hairline dark:border-hairline-dark overflow-hidden">
              {results.map((r) => (
                <button
                  key={r.id}
                  onClick={() => { setSelected(r); setActiveTab("timeline"); }}
                  className="w-full flex items-center gap-4 px-4 py-3 border-b border-hairline dark:border-hairline-dark last:border-0 hover:bg-hairline/40 dark:hover:bg-hairline-dark/40 transition-colors text-left"
                >
                  <span className="font-mono font-semibold text-sm text-ink dark:text-bone w-36 shrink-0">
                    {r.text}
                  </span>
                  <span className="text-[11px] text-steel capitalize w-24 shrink-0">{r.format_class}</span>
                  {r.vehicle?.color ? (
                    <span className="inline-flex items-center gap-1.5">
                      <span
                        className="w-3 h-3 rounded-full border border-hairline dark:border-hairline-dark shrink-0"
                        style={{ backgroundColor: COLOR_HEX[r.vehicle.color] ?? "#6b7280" }}
                      />
                      <span className="text-xs text-steel capitalize">{r.vehicle.color}</span>
                    </span>
                  ) : (
                    <span className="text-xs text-steel/50">no color</span>
                  )}
                  {r.vehicle?.type && (
                    <span className="text-xs text-steel capitalize">{r.vehicle.type}</span>
                  )}
                  <span className="ml-auto text-xs text-signal">View →</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Detail panel */}
      {selected && (
        <div className="space-y-4">
          {/* Selected plate header */}
          <div className="flex items-center flex-wrap gap-3">
            <button
              onClick={() => setSelected(null)}
              className="text-xs text-steel hover:text-ink dark:hover:text-bone transition-colors"
            >
              ← Back
            </button>
            <span className="font-mono font-semibold text-lg text-ink dark:text-bone">
              {selected.text}
            </span>
            {selected.vehicle?.color && (
              <span className="inline-flex items-center gap-1.5">
                <span
                  className="w-3.5 h-3.5 rounded-full border border-hairline dark:border-hairline-dark shrink-0"
                  style={{ backgroundColor: COLOR_HEX[selected.vehicle.color] ?? "#6b7280" }}
                />
                <span className="text-xs text-steel capitalize">{selected.vehicle.color}</span>
              </span>
            )}
            {selected.vehicle?.type && (
              <span className="text-xs text-steel capitalize">{selected.vehicle.type}</span>
            )}
            {selected.vehicle?.last_seen && (
              <span className="text-xs text-steel ml-auto">
                last seen {relativeTime(selected.vehicle.last_seen)}
              </span>
            )}
          </div>

          {/* Tabs */}
          <div className="flex gap-1 border-b border-hairline dark:border-hairline-dark">
            {(["timeline", "sightings"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 text-sm transition-colors -mb-px border-b-2 ${
                  activeTab === tab
                    ? "border-signal text-signal"
                    : "border-transparent text-steel hover:text-ink dark:hover:text-bone"
                }`}
              >
                {tab === "timeline" ? "Timeline" : "Camera sightings"}
              </button>
            ))}
          </div>

          {/* Timeline */}
          {activeTab === "timeline" && (
            <div className="rounded-[12px] border border-hairline dark:border-hairline-dark overflow-hidden">
              {loadingTimeline && <p className="text-xs text-steel p-4">Loading…</p>}
              {!loadingTimeline && (timeline?.items.length ?? 0) === 0 && (
                <p className="text-xs text-steel p-4">No events in the last 30 days.</p>
              )}
              {(timeline?.items.length ?? 0) > 0 && (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-hairline dark:border-hairline-dark bg-hairline/40 dark:bg-hairline-dark/40">
                      <th className="text-left px-4 py-2 text-xs font-semibold text-steel">Time</th>
                      <th className="text-left px-4 py-2 text-xs font-semibold text-steel">Camera</th>
                      <th className="text-left px-4 py-2 text-xs font-semibold text-steel">Kind</th>
                      <th className="text-left px-4 py-2 text-xs font-semibold text-steel">Conf.</th>
                      <th className="px-4 py-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {timeline!.items.map((e) => (
                      <tr
                        key={e.id}
                        className="border-b border-hairline dark:border-hairline-dark last:border-0 hover:bg-hairline/30 dark:hover:bg-hairline-dark/30 transition-colors"
                      >
                        <td className="px-4 py-2">
                          <span className="font-mono text-xs text-ink dark:text-bone">{formatTs(e.ts)}</span>
                          <span className="block text-[10px] text-steel">{relativeTime(e.ts)}</span>
                        </td>
                        <td className="px-4 py-2 text-xs text-steel">
                          {e.camera_name ?? `${e.camera_id.slice(0, 8)}…`}
                        </td>
                        <td className="px-4 py-2">
                          <KindChip kind={e.kind} />
                        </td>
                        <td className="px-4 py-2 text-xs tabular-nums text-steel">
                          {e.confidence != null ? `${(e.confidence * 100).toFixed(0)}%` : "—"}
                        </td>
                        <td className="px-4 py-2">
                          {e.snapshot_key && (
                            <a
                              href={`${API_BASE}/events/${e.id}/snapshot`}
                              target="_blank"
                              rel="noreferrer"
                              className="text-xs text-signal hover:underline"
                            >
                              Snapshot
                            </a>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {timeline?.next_cursor && (
                <p className="text-[11px] text-steel text-center p-3">Showing first 100 results.</p>
              )}
            </div>
          )}

          {/* Camera sightings */}
          {activeTab === "sightings" && (
            <div className="rounded-[12px] border border-hairline dark:border-hairline-dark overflow-hidden">
              {loadingSightings && <p className="text-xs text-steel p-4">Loading…</p>}
              {!loadingSightings && sightings.length === 0 && (
                <p className="text-xs text-steel p-4">No sightings in the last 30 days.</p>
              )}
              {sightings.length > 0 && (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-hairline dark:border-hairline-dark bg-hairline/40 dark:bg-hairline-dark/40">
                      <th className="text-left px-4 py-2 text-xs font-semibold text-steel">Camera</th>
                      <th className="text-left px-4 py-2 text-xs font-semibold text-steel">Reads</th>
                      <th className="text-left px-4 py-2 text-xs font-semibold text-steel">First seen</th>
                      <th className="text-left px-4 py-2 text-xs font-semibold text-steel">Last seen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sightings.map((s) => (
                      <tr
                        key={s.camera_id}
                        className="border-b border-hairline dark:border-hairline-dark last:border-0 hover:bg-hairline/30 dark:hover:bg-hairline-dark/30 transition-colors"
                      >
                        <td className="px-4 py-2 text-xs font-medium text-ink dark:text-bone">{s.name}</td>
                        <td className="px-4 py-2 text-xs tabular-nums font-semibold text-signal">{s.count}</td>
                        <td className="px-4 py-2 text-xs text-steel">
                          <span title={formatTs(s.first_seen)}>{relativeTime(s.first_seen)}</span>
                        </td>
                        <td className="px-4 py-2 text-xs text-steel">
                          <span title={formatTs(s.last_seen)}>{relativeTime(s.last_seen)}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
