"use client";

import { useState } from "react";
import { useAuthStore } from "@/store/auth";
import { API_BASE } from "@/lib/api";

const REPORTS = [
  {
    key: "events",
    label: "Events",
    desc: "All plate reads and events for the selected date range",
    endpoint: "/reports/events.csv",
    ext: "csv",
  },
  {
    key: "parking",
    label: "Parking sessions",
    desc: "Session-by-session log with duration, amount and payment status",
    endpoint: "/reports/parking.csv",
    ext: "csv",
  },
  {
    key: "alerts",
    label: "Alerts",
    desc: "All watchlist alerts with status and acknowledgement details",
    endpoint: "/reports/alerts.csv",
    ext: "csv",
  },
] as const;

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}
function offsetDays(n: number) {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

export default function ReportsPage() {
  const { accessToken } = useAuthStore();
  const [from, setFrom] = useState(offsetDays(-7));
  const [to, setTo] = useState(todayStr());
  const [pdfDate, setPdfDate] = useState(offsetDays(-1));
  const [loading, setLoading] = useState<string | null>(null);

  async function download(endpoint: string, filename: string) {
    if (!accessToken) return;
    setLoading(filename);
    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!res.ok) throw new Error(res.statusText);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(null);
    }
  }

  function csvUrl(endpoint: string) {
    return `${endpoint}?from=${from}&to=${to}`;
  }

  return (
    <div className="p-8 max-w-3xl">
      <h1 className="text-2xl font-bold text-ink dark:text-bone mb-1">Reports</h1>
      <p className="text-sm text-steel mb-8">Export data as CSV or download a PDF daily summary.</p>

      {/* Date range */}
      <section className="mb-8">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-steel mb-3">Date range (CSV exports)</h2>
        <div className="flex gap-3 items-center">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-steel">From</label>
            <input
              type="date"
              value={from}
              max={to}
              onChange={(e) => setFrom(e.target.value)}
              className="border border-hairline dark:border-hairline-dark rounded-lg px-3 py-2 text-sm bg-bone dark:bg-surface text-ink dark:text-bone focus:outline-none focus:ring-2 focus:ring-signal"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-steel">To</label>
            <input
              type="date"
              value={to}
              min={from}
              max={todayStr()}
              onChange={(e) => setTo(e.target.value)}
              className="border border-hairline dark:border-hairline-dark rounded-lg px-3 py-2 text-sm bg-bone dark:bg-surface text-ink dark:text-bone focus:outline-none focus:ring-2 focus:ring-signal"
            />
          </div>
        </div>
      </section>

      {/* CSV exports */}
      <section className="mb-8">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-steel mb-3">CSV exports</h2>
        <div className="flex flex-col gap-3">
          {REPORTS.map((r) => {
            const filename = `${r.key}_${from}_${to}.csv`;
            const busy = loading === filename;
            return (
              <div
                key={r.key}
                className="flex items-center justify-between bg-bone dark:bg-surface border border-hairline dark:border-hairline-dark rounded-xl px-5 py-4"
              >
                <div>
                  <p className="font-semibold text-sm text-ink dark:text-bone">{r.label}</p>
                  <p className="text-xs text-steel mt-0.5">{r.desc}</p>
                </div>
                <button
                  onClick={() => download(csvUrl(r.endpoint), filename)}
                  disabled={busy}
                  className="ml-4 shrink-0 px-4 py-2 rounded-lg text-sm font-semibold bg-signal text-white hover:bg-signal/90 disabled:opacity-50 transition-colors"
                >
                  {busy ? "Downloading…" : "Download CSV"}
                </button>
              </div>
            );
          })}
        </div>
      </section>

      {/* PDF daily summary */}
      <section>
        <h2 className="text-xs font-semibold uppercase tracking-widest text-steel mb-3">PDF daily summary</h2>
        <div className="bg-bone dark:bg-surface border border-hairline dark:border-hairline-dark rounded-xl px-5 py-4">
          <p className="text-xs text-steel mb-3">
            One-page summary with traffic overview, parking revenue, alert counts, top plates and hourly breakdown.
          </p>
          <div className="flex gap-3 items-end">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-steel">Date</label>
              <input
                type="date"
                value={pdfDate}
                max={offsetDays(-1)}
                onChange={(e) => setPdfDate(e.target.value)}
                className="border border-hairline dark:border-hairline-dark rounded-lg px-3 py-2 text-sm bg-bone dark:bg-surface text-ink dark:text-bone focus:outline-none focus:ring-2 focus:ring-signal"
              />
            </div>
            <button
              onClick={() => {
                const filename = `daily_summary_${pdfDate}.pdf`;
                download(`/reports/daily-summary.pdf?date=${pdfDate}`, filename);
              }}
              disabled={loading !== null}
              className="px-4 py-2 rounded-lg text-sm font-semibold bg-ink dark:bg-bone text-bone dark:text-ink hover:opacity-90 disabled:opacity-50 transition-colors"
            >
              {loading?.endsWith(".pdf") ? "Generating…" : "Download PDF"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
