"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useAuthStore } from "@/store/auth";
import { api, Alert, AlertStatus } from "@/lib/api";
import { formatTs, relativeTime } from "@/lib/utils";
import { PlateStrip } from "@/components/ui/plate-strip";

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

const STATUS_STYLES: Record<AlertStatus, string> = {
  new: "bg-alert/15 text-alert border border-alert/30",
  ack: "bg-steel/15 text-steel border border-steel/30",
  snoozed: "bg-signal/15 text-signal border border-signal/30",
  resolved: "bg-confirm/15 text-confirm border border-confirm/30",
};

export default function AlertsPage() {
  const { accessToken } = useAuthStore();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<AlertStatus | "all">("new");
  const [newIds, setNewIds] = useState<Set<string>>(new Set());
  const wsRef = useRef<WebSocket | null>(null);

  const fetchAlerts = useCallback(async () => {
    if (!accessToken) return;
    try {
      const page = await api.alerts.list(accessToken, {
        status: filter === "all" ? undefined : filter,
        limit: 100,
      });
      setAlerts(page.items);
    } catch {
      // silently retry on next WS event
    } finally {
      setLoading(false);
    }
  }, [accessToken, filter]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  // WebSocket — listen for live alert events
  useEffect(() => {
    if (!accessToken) return;
    const ws = new WebSocket(`${WS_BASE}/ws/alerts`);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data);
        const id: string = payload.alert_id;
        setNewIds((prev) => new Set(prev).add(id));
        setTimeout(() => setNewIds((prev) => { const s = new Set(prev); s.delete(id); return s; }), 3000);
        // Refresh list to get the new alert row
        fetchAlerts();
      } catch {}
    };

    return () => ws.close();
  }, [accessToken, fetchAlerts]);

  async function handleAck(id: string) {
    if (!accessToken) return;
    await api.alerts.ack(accessToken, id);
    fetchAlerts();
  }

  async function handleSnooze(id: string) {
    if (!accessToken) return;
    const until = new Date(Date.now() + 60 * 60 * 1000).toISOString(); // 1 hour
    await api.alerts.snooze(accessToken, id, until);
    fetchAlerts();
  }

  async function handleResolve(id: string) {
    if (!accessToken) return;
    await api.alerts.resolve(accessToken, id);
    fetchAlerts();
  }

  const FILTERS: Array<AlertStatus | "all"> = ["all", "new", "ack", "snoozed", "resolved"];

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-medium text-ink dark:text-bone">Alerts</h1>
        <div className="flex gap-1">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                filter === f
                  ? "bg-signal text-white"
                  : "text-steel hover:text-ink dark:hover:text-bone"
              }`}
            >
              {f === "all" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <p className="text-sm text-steel">Loading…</p>
      ) : alerts.length === 0 ? (
        <div className="text-center py-20 text-steel text-sm">
          No alerts. Add watchlist entries to start monitoring.
        </div>
      ) : (
        <div className="space-y-2">
          {alerts.map((alert) => (
            <AlertRow
              key={alert.id}
              alert={alert}
              isNew={newIds.has(alert.id)}
              onAck={() => handleAck(alert.id)}
              onSnooze={() => handleSnooze(alert.id)}
              onResolve={() => handleResolve(alert.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function AlertRow({
  alert,
  isNew,
  onAck,
  onSnooze,
  onResolve,
}: {
  alert: Alert;
  isNew: boolean;
  onAck: () => void;
  onSnooze: () => void;
  onResolve: () => void;
}) {
  return (
    <div
      className={`flex items-center gap-4 p-3 rounded-lg border transition-all ${
        isNew
          ? "border-alert/60 bg-alert/5 animate-plate-pulse"
          : "border-hairline dark:border-hairline-dark bg-white dark:bg-ink/40"
      }`}
    >
      {/* Plate */}
      <div className="shrink-0">
        {alert.plate_text ? (
          <PlateStrip text={alert.plate_text} confidence={1} isNew={isNew} />
        ) : (
          <span className="text-xs text-steel">—</span>
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${STATUS_STYLES[alert.status]}`}>
            {alert.status}
          </span>
          {alert.watchlist_name && (
            <span className="text-xs text-steel">{alert.watchlist_name}</span>
          )}
        </div>
        <p className="text-[11px] text-steel mt-0.5">
          {formatTs(alert.created_at)} · {relativeTime(alert.created_at)}
        </p>
      </div>

      {/* Actions — only show for actionable statuses */}
      {(alert.status === "new" || alert.status === "snoozed") && (
        <div className="flex items-center gap-2 shrink-0">
          <ActionBtn label="Ack" onClick={onAck} />
          {alert.status === "new" && <ActionBtn label="Snooze 1h" onClick={onSnooze} />}
          <ActionBtn label="Resolve" onClick={onResolve} variant="confirm" />
        </div>
      )}
    </div>
  );
}

function ActionBtn({
  label,
  onClick,
  variant = "default",
}: {
  label: string;
  onClick: () => void;
  variant?: "default" | "confirm";
}) {
  return (
    <button
      onClick={onClick}
      className={`px-2 py-1 rounded text-[11px] font-medium transition-colors ${
        variant === "confirm"
          ? "bg-confirm/15 text-confirm hover:bg-confirm/25"
          : "bg-steel/10 text-steel hover:bg-steel/20"
      }`}
    >
      {label}
    </button>
  );
}
