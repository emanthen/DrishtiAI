"use client";

import { useEffect, useState, useCallback } from "react";
import {
  BarChart, Bar, AreaChart, Area,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { useAuthStore } from "@/store/auth";
import {
  api,
  AnalyticsOverview, HourlyBucket, DailyRevenue, OccupancyBucket, TopPlate,
  Site,
} from "@/lib/api";

// ── Palette tokens (must match Tailwind config) ───────────────────────────────
const SIGNAL  = "#3B82F6";
const CONFIRM = "#22C55E";
const ALERT   = "#EF4444";
const STEEL   = "#94A3B8";

const HOUR_LABELS = ["12a","1","2","3","4","5","6","7","8","9","10","11",
                     "12p","1","2","3","4","5","6","7","8","9","10","11"];

// ── Stat card ─────────────────────────────────────────────────────────────────
function StatCard({
  label, value, sub, accent = false,
}: { label: string; value: string | number; sub?: string; accent?: boolean }) {
  return (
    <div className="rounded-xl border border-hairline dark:border-hairline-dark bg-white dark:bg-ink/40 px-5 py-4">
      <p className="text-xs text-steel mb-1">{label}</p>
      <p className={`text-2xl font-semibold tabular-nums ${accent ? "text-alert" : "text-ink dark:text-bone"}`}>
        {value}
      </p>
      {sub && <p className="text-[11px] text-steel mt-0.5">{sub}</p>}
    </div>
  );
}

// ── Tooltip styles ────────────────────────────────────────────────────────────
const TooltipStyle = {
  contentStyle: {
    background: "#1E293B",
    border: "1px solid #334155",
    borderRadius: 8,
    fontSize: 12,
    color: "#F1F5F9",
  },
  cursor: { fill: "rgba(148,163,184,0.08)" },
};

// ── Page ──────────────────────────────────────────────────────────────────────
export default function AnalyticsPage() {
  const { accessToken } = useAuthStore();
  const [sites, setSites] = useState<Site[]>([]);
  const [siteId, setSiteId] = useState<string | undefined>(undefined);

  const [overview, setOverview]       = useState<AnalyticsOverview | null>(null);
  const [hourly, setHourly]           = useState<HourlyBucket[]>([]);
  const [revenue, setRevenue]         = useState<DailyRevenue[]>([]);
  const [occupancy, setOccupancy]     = useState<OccupancyBucket[]>([]);
  const [topPlates, setTopPlates]     = useState<TopPlate[]>([]);
  const [loading, setLoading]         = useState(true);

  // Fetch site list once
  useEffect(() => {
    if (!accessToken) return;
    api.sites.list(accessToken).then((list) => {
      setSites(list);
      if (list.length > 0) setSiteId(list[0].id);
    }).catch(() => {});
  }, [accessToken]);

  const fetchAll = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      const [ov, hr, rv, oc, tp] = await Promise.all([
        api.analytics.overview(accessToken, siteId),
        api.analytics.hourlyTraffic(accessToken, siteId, 7),
        api.analytics.dailyRevenue(accessToken, siteId, 14),
        api.analytics.occupancy(accessToken, siteId),
        api.analytics.topPlates(accessToken, siteId, 30, 10),
      ]);
      setOverview(ov);
      setHourly(hr);
      setRevenue(rv);
      setOccupancy(oc);
      setTopPlates(tp);
    } catch {
      // silent — partial data is fine
    } finally {
      setLoading(false);
    }
  }, [accessToken, siteId]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const maxPlateCount = topPlates[0]?.count ?? 1;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-medium text-ink dark:text-bone">Analytics</h1>
        <div className="flex items-center gap-3">
          {sites.length > 1 && (
            <select
              value={siteId ?? ""}
              onChange={(e) => setSiteId(e.target.value || undefined)}
              className="px-3 py-1.5 rounded border border-hairline dark:border-hairline-dark bg-white dark:bg-ink text-sm text-ink dark:text-bone focus:outline-none focus:ring-1 focus:ring-signal"
            >
              {sites.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          )}
          <button
            onClick={fetchAll}
            className="px-3 py-1.5 rounded border border-hairline dark:border-hairline-dark text-xs text-steel hover:text-ink dark:hover:text-bone transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      {loading && !overview ? (
        <p className="text-sm text-steel py-20 text-center">Loading…</p>
      ) : (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-4">
            <StatCard label="Events today"       value={overview?.events_today ?? 0} />
            <StatCard label="Active sessions"    value={overview?.active_sessions ?? 0} sub="vehicles parked now" />
            <StatCard
              label="Revenue today"
              value={`NPR ${((overview?.revenue_today ?? 0)).toFixed(0)}`}
              sub="from closed sessions"
            />
            <StatCard
              label="Open alerts"
              value={overview?.open_alerts ?? 0}
              accent={(overview?.open_alerts ?? 0) > 0}
            />
            <StatCard label="Gate triggers"     value={overview?.gate_triggers_today ?? 0} sub="today" />
            <StatCard label="Active passes"     value={overview?.active_passes ?? 0}      sub="visitor passes now valid" />
          </div>

          {/* Charts row 1 */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {/* Hourly traffic */}
            <ChartCard title="Hourly traffic" sub="plate reads by hour of day · last 7 days">
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={hourly} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.12)" />
                  <XAxis
                    dataKey="hour"
                    tickFormatter={(h: number) => HOUR_LABELS[h]}
                    tick={{ fontSize: 10, fill: STEEL }}
                    interval={2}
                  />
                  <YAxis tick={{ fontSize: 10, fill: STEEL }} allowDecimals={false} />
                  <Tooltip
                    {...TooltipStyle}
                    formatter={(v: number) => [v, "reads"]}
                    labelFormatter={(h: number) => `${HOUR_LABELS[h]}:00`}
                  />
                  <Bar dataKey="count" fill={SIGNAL} radius={[3, 3, 0, 0]} maxBarSize={24} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            {/* Daily revenue */}
            <ChartCard title="Daily revenue" sub="NPR · last 14 days">
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={revenue} margin={{ top: 4, right: 8, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.12)" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(d: string) => d.slice(5)}
                    tick={{ fontSize: 10, fill: STEEL }}
                    interval="preserveStartEnd"
                  />
                  <YAxis tick={{ fontSize: 10, fill: STEEL }} allowDecimals={false} />
                  <Tooltip
                    {...TooltipStyle}
                    formatter={(v: number, name: string) => [
                      name === "revenue" ? `NPR ${v.toFixed(0)}` : v,
                      name === "revenue" ? "Revenue" : "Sessions",
                    ]}
                  />
                  <Bar dataKey="revenue"  fill={CONFIRM}  radius={[3,3,0,0]} maxBarSize={24} />
                  <Bar dataKey="sessions" fill={SIGNAL}   radius={[3,3,0,0]} maxBarSize={24} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>

          {/* Occupancy trend */}
          {occupancy.length > 0 && (
            <ChartCard title="Occupancy — last 24 h" sub="entries and exits per hour">
              <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={occupancy} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="entryGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor={SIGNAL}  stopOpacity={0.3} />
                      <stop offset="95%" stopColor={SIGNAL}  stopOpacity={0}   />
                    </linearGradient>
                    <linearGradient id="exitGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor={CONFIRM} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={CONFIRM} stopOpacity={0}   />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.12)" />
                  <XAxis
                    dataKey="hour"
                    tickFormatter={(h: string) => h.slice(11, 16)}
                    tick={{ fontSize: 10, fill: STEEL }}
                    interval="preserveStartEnd"
                  />
                  <YAxis tick={{ fontSize: 10, fill: STEEL }} allowDecimals={false} />
                  <Tooltip
                    {...TooltipStyle}
                    labelFormatter={(h: string) => h.slice(0, 16).replace("T", " ")}
                  />
                  <Area dataKey="entries" stroke={SIGNAL}  fill="url(#entryGrad)" strokeWidth={2} dot={false} />
                  <Area dataKey="exits"   stroke={CONFIRM} fill="url(#exitGrad)"  strokeWidth={2} dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </ChartCard>
          )}

          {/* Top plates */}
          {topPlates.length > 0 && (
            <ChartCard title="Top plates" sub="most seen in last 30 days">
              <div className="space-y-2 pt-1">
                {topPlates.map((p, i) => (
                  <div key={p.plate_text} className="flex items-center gap-3">
                    <span className="text-[11px] text-steel w-4 text-right shrink-0">{i + 1}</span>
                    <span className="font-mono text-xs text-ink dark:text-bone w-28 shrink-0">
                      {p.plate_text}
                    </span>
                    <div className="flex-1 bg-hairline dark:bg-hairline-dark rounded-full h-2 overflow-hidden">
                      <div
                        className="h-2 rounded-full bg-signal transition-all"
                        style={{ width: `${Math.round((p.count / maxPlateCount) * 100)}%` }}
                      />
                    </div>
                    <span className="text-xs tabular-nums text-steel w-8 text-right shrink-0">
                      {p.count}
                    </span>
                  </div>
                ))}
              </div>
            </ChartCard>
          )}
        </>
      )}
    </div>
  );
}

function ChartCard({
  title, sub, children,
}: { title: string; sub: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-hairline dark:border-hairline-dark bg-white dark:bg-ink/40 px-5 py-4">
      <p className="text-sm font-medium text-ink dark:text-bone">{title}</p>
      <p className="text-[11px] text-steel mb-3">{sub}</p>
      {children}
    </div>
  );
}
