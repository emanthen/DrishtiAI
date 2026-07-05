"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/auth";
import { api, type RetentionPolicy } from "@/lib/api";

const DATA_CLASSES = ["plate_events", "snapshots", "clips", "continuous_recording", "audit_logs"] as const;

function StatusDot({ status }: { status: "ok" | "error" }) {
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full shrink-0 ${
        status === "ok" ? "bg-confirm" : "bg-alert"
      }`}
    />
  );
}

function HealthCard({ label, status, detail }: { label: string; status: "ok" | "error"; detail: string | null }) {
  return (
    <div className={`rounded-lg border px-4 py-3 flex flex-col gap-1 ${
      status === "ok"
        ? "border-hairline dark:border-hairline-dark bg-white dark:bg-ink/40"
        : "border-alert/40 bg-alert/5"
    }`}>
      <div className="flex items-center gap-2">
        <StatusDot status={status} />
        <p className="text-sm font-medium text-ink dark:text-bone capitalize">{label}</p>
      </div>
      {detail && <p className="text-[11px] text-steel truncate" title={detail}>{detail}</p>}
    </div>
  );
}

export default function SystemPage() {
  const { accessToken } = useAuthStore();
  const qc = useQueryClient();
  const [dropMonths, setDropMonths] = useState(12);
  const [dropConfirm, setDropConfirm] = useState(false);
  const [selectedSite, setSelectedSite] = useState<string>("");
  const [editingPolicy, setEditingPolicy] = useState<{ data_class: string; retain_days: number } | null>(null);

  const { data: health, isLoading: loadingHealth } = useQuery({
    queryKey: ["system-health"],
    queryFn: () => api.system.health(accessToken!),
    enabled: !!accessToken,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });

  const { data: dbStats, isLoading: loadingStats } = useQuery({
    queryKey: ["system-db-stats"],
    queryFn: () => api.system.dbStats(accessToken!),
    enabled: !!accessToken,
    staleTime: 60_000,
  });

  const { data: sites = [] } = useQuery({
    queryKey: ["sites"],
    queryFn: () => api.sites.list(accessToken!),
    enabled: !!accessToken,
    staleTime: 120_000,
  });

  const { data: policies = [] } = useQuery({
    queryKey: ["retention-policies", selectedSite],
    queryFn: () => api.system.retentionPolicies(accessToken!, selectedSite || undefined),
    enabled: !!accessToken,
    staleTime: 30_000,
  });

  const dropMutation = useMutation({
    mutationFn: () => api.system.dropOldPartitions(accessToken!, dropMonths),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["system-db-stats"] });
      qc.invalidateQueries({ queryKey: ["system-health"] });
      setDropConfirm(false);
    },
  });

  const savePolicyMutation = useMutation({
    mutationFn: (body: { site_id: string; data_class: string; retain_days: number }) =>
      api.system.upsertRetentionPolicy(accessToken!, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["retention-policies"] });
      setEditingPolicy(null);
    },
  });

  const healthComponents = health
    ? [
        { label: "API",        ...health.api },
        { label: "Database",   ...health.database },
        { label: "Redis",      ...health.redis },
        { label: "MinIO",      ...health.minio },
        { label: "Pipeline",   ...health.pipeline },
        { label: "Partitions", ...health.partitions },
      ]
    : [];

  const policyMap: Record<string, RetentionPolicy> = {};
  for (const p of policies) policyMap[p.data_class] = p;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-8">
      <h1 className="text-lg font-medium text-ink dark:text-bone">System</h1>

      {/* Health */}
      <section>
        <h2 className="text-xs font-semibold text-steel uppercase tracking-wide mb-3">Health</h2>
        {loadingHealth ? (
          <p className="text-xs text-steel">Loading…</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
            {healthComponents.map((c) => (
              <HealthCard key={c.label} label={c.label} status={c.status} detail={c.detail ?? null} />
            ))}
          </div>
        )}
      </section>

      {/* Event partitions */}
      <section>
        <h2 className="text-xs font-semibold text-steel uppercase tracking-wide mb-3">
          Event partitions
          {dbStats && (
            <span className="ml-2 text-steel/60 normal-case font-normal">
              ~{dbStats.total_event_estimate.toLocaleString()} total rows (estimate)
            </span>
          )}
        </h2>
        {loadingStats ? (
          <p className="text-xs text-steel">Loading…</p>
        ) : (
          <>
            <div className="rounded-[12px] border border-hairline dark:border-hairline-dark overflow-hidden mb-4">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-hairline dark:border-hairline-dark bg-hairline/40 dark:bg-hairline-dark/40">
                    <th className="text-left px-4 py-2 text-xs font-semibold text-steel">Partition</th>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-steel">Range</th>
                    <th className="text-right px-4 py-2 text-xs font-semibold text-steel">~Rows</th>
                  </tr>
                </thead>
                <tbody>
                  {(dbStats?.partitions ?? []).map((p) => (
                    <tr
                      key={p.name}
                      className="border-b border-hairline dark:border-hairline-dark last:border-0"
                    >
                      <td className="px-4 py-2 font-mono text-xs text-ink dark:text-bone">{p.name}</td>
                      <td className="px-4 py-2 text-xs text-steel">{p.bounds}</td>
                      <td className="px-4 py-2 text-xs tabular-nums text-steel text-right">
                        {p.row_estimate.toLocaleString()}
                      </td>
                    </tr>
                  ))}
                  {(dbStats?.partitions.length ?? 0) === 0 && (
                    <tr>
                      <td colSpan={3} className="px-4 py-4 text-xs text-steel text-center">
                        No partitions found — run migration 0007.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Drop old partitions */}
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-xs text-steel">Drop partitions older than</span>
              <input
                type="number"
                min={1}
                max={120}
                value={dropMonths}
                onChange={(e) => { setDropMonths(Number(e.target.value)); setDropConfirm(false); }}
                className="w-16 rounded border border-hairline dark:border-hairline-dark bg-white dark:bg-ink px-2 py-1 text-xs text-ink dark:text-bone focus:outline-none focus:ring-1 focus:ring-signal"
              />
              <span className="text-xs text-steel">months</span>
              {!dropConfirm ? (
                <button
                  onClick={() => setDropConfirm(true)}
                  className="px-3 py-1.5 rounded text-xs font-medium border border-alert/40 text-alert hover:bg-alert/10 transition-colors"
                >
                  Drop old partitions…
                </button>
              ) : (
                <>
                  <span className="text-xs text-alert font-medium">Are you sure? This is irreversible.</span>
                  <button
                    onClick={() => dropMutation.mutate()}
                    disabled={dropMutation.isPending}
                    className="px-3 py-1.5 rounded text-xs font-semibold bg-alert text-white hover:bg-alert/90 disabled:opacity-50 transition-colors"
                  >
                    {dropMutation.isPending ? "Dropping…" : "Confirm drop"}
                  </button>
                  <button
                    onClick={() => setDropConfirm(false)}
                    className="text-xs text-steel hover:text-ink transition-colors"
                  >
                    Cancel
                  </button>
                </>
              )}
              {dropMutation.isSuccess && (
                <span className="text-xs text-confirm">
                  Dropped: {(dropMutation.data?.dropped.length ?? 0) === 0
                    ? "none (nothing old enough)"
                    : dropMutation.data?.dropped.join(", ")}
                </span>
              )}
            </div>
          </>
        )}
      </section>

      {/* Retention policies */}
      <section>
        <div className="flex items-center gap-3 mb-3">
          <h2 className="text-xs font-semibold text-steel uppercase tracking-wide">Retention policies</h2>
          {sites.length > 1 && (
            <select
              value={selectedSite}
              onChange={(e) => setSelectedSite(e.target.value)}
              className="ml-auto rounded border border-hairline dark:border-hairline-dark bg-white dark:bg-ink px-2 py-1 text-xs text-ink dark:text-bone focus:outline-none focus:ring-1 focus:ring-signal"
            >
              <option value="">All sites</option>
              {sites.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          )}
        </div>

        {sites.length === 0 ? (
          <p className="text-xs text-steel">No sites found.</p>
        ) : (
          <div className="space-y-4">
            {(selectedSite ? sites.filter((s) => s.id === selectedSite) : sites).map((site) => (
              <div key={site.id}>
                <p className="text-xs font-medium text-ink dark:text-bone mb-2">{site.name}</p>
                <div className="rounded-[12px] border border-hairline dark:border-hairline-dark overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-hairline dark:border-hairline-dark bg-hairline/40 dark:bg-hairline-dark/40">
                        <th className="text-left px-4 py-2 text-xs font-semibold text-steel">Data class</th>
                        <th className="text-left px-4 py-2 text-xs font-semibold text-steel">Retain (days)</th>
                        <th className="px-4 py-2" />
                      </tr>
                    </thead>
                    <tbody>
                      {DATA_CLASSES.map((dc) => {
                        const existing = policies.find((p) => p.site_id === site.id && p.data_class === dc);
                        const isEditing = editingPolicy !== null && editingPolicy.data_class === dc;
                        return (
                          <tr key={dc} className="border-b border-hairline dark:border-hairline-dark last:border-0">
                            <td className="px-4 py-2 text-xs font-mono text-ink dark:text-bone">{dc}</td>
                            <td className="px-4 py-2">
                              {isEditing ? (
                                <input
                                  type="number"
                                  min={1}
                                  value={editingPolicy!.retain_days}
                                  onChange={(e) => setEditingPolicy({ ...editingPolicy!, retain_days: Number(e.target.value) })}
                                  className="w-20 rounded border border-signal px-2 py-0.5 text-xs text-ink dark:text-bone bg-white dark:bg-ink focus:outline-none"
                                />
                              ) : (
                                <span className="text-xs text-steel">
                                  {existing ? `${existing.retain_days} days` : <span className="italic text-steel/50">not set</span>}
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-2 text-right">
                              {isEditing ? (
                                <span className="flex items-center gap-2 justify-end">
                                  <button
                                    onClick={() => savePolicyMutation.mutate({
                                      site_id: site.id,
                                      data_class: dc,
                                      retain_days: editingPolicy!.retain_days,
                                    })}
                                    disabled={savePolicyMutation.isPending}
                                    className="text-xs text-signal hover:underline disabled:opacity-50"
                                  >
                                    Save
                                  </button>
                                  <button onClick={() => setEditingPolicy(null)} className="text-xs text-steel hover:underline">
                                    Cancel
                                  </button>
                                </span>
                              ) : (
                                <button
                                  onClick={() => setEditingPolicy({ data_class: dc, retain_days: existing?.retain_days ?? 90 })}
                                  className="text-xs text-signal hover:underline"
                                >
                                  {existing ? "Edit" : "Set"}
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
