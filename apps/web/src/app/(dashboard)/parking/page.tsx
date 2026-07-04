"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useAuthStore } from "@/store/auth";
import { api, ParkingSession, PaymentStatus } from "@/lib/api";
import { formatTs, relativeTime } from "@/lib/utils";
import { PlateStrip } from "@/components/ui/plate-strip";

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

const PAYMENT_STYLES: Record<PaymentStatus, string> = {
  pending: "bg-signal/15 text-signal border border-signal/30",
  paid: "bg-confirm/15 text-confirm border border-confirm/30",
  waived: "bg-steel/15 text-steel border border-steel/30",
  failed: "bg-alert/15 text-alert border border-alert/30",
};

function useLiveDuration(entryTs: string | null): string {
  const [secs, setSecs] = useState(0);

  useEffect(() => {
    if (!entryTs) return;
    const start = new Date(entryTs).getTime();
    const tick = () => setSecs(Math.max(0, Math.floor((Date.now() - start) / 1000)));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [entryTs]);

  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

type Tab = "active" | "all";

export default function ParkingPage() {
  const { accessToken } = useAuthStore();
  const [tab, setTab] = useState<Tab>("active");
  const [sessions, setSessions] = useState<ParkingSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [newIds, setNewIds] = useState<Set<string>>(new Set());
  const wsRef = useRef<WebSocket | null>(null);

  const fetchSessions = useCallback(async () => {
    if (!accessToken) return;
    try {
      if (tab === "active") {
        setSessions(await api.parking.listActive(accessToken));
      } else {
        const page = await api.parking.list(accessToken, { limit: 100 });
        setSessions(page.items);
      }
    } catch {
      // silent retry on next WS event
    } finally {
      setLoading(false);
    }
  }, [accessToken, tab]);

  useEffect(() => {
    setLoading(true);
    fetchSessions();
  }, [fetchSessions]);

  // WebSocket — refresh on session open/close events
  useEffect(() => {
    if (!accessToken) return;
    const ws = new WebSocket(`${WS_BASE}/ws/parking`);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data);
        const id: string = payload.session_id;
        if (payload.event === "session_opened") {
          setNewIds((prev) => new Set(prev).add(id));
          setTimeout(() => setNewIds((prev) => { const s = new Set(prev); s.delete(id); return s; }), 3000);
        }
        fetchSessions();
      } catch {}
    };

    return () => ws.close();
  }, [accessToken, fetchSessions]);

  async function handleClose(id: string) {
    if (!accessToken) return;
    await api.parking.close(accessToken, id);
    fetchSessions();
  }

  async function handleMarkPaid(id: string) {
    if (!accessToken) return;
    await api.parking.markPaid(accessToken, id);
    fetchSessions();
  }

  async function handleWaive(id: string) {
    if (!accessToken) return;
    await api.parking.waive(accessToken, id);
    fetchSessions();
  }

  const TABS: Array<{ key: Tab; label: string }> = [
    { key: "active", label: "Active" },
    { key: "all", label: "All sessions" },
  ];

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-medium text-ink dark:text-bone">Parking</h1>
        <div className="flex gap-1">
          {TABS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                tab === key
                  ? "bg-signal text-white"
                  : "text-steel hover:text-ink dark:hover:text-bone"
              }`}
            >
              {label}
              {key === "active" && sessions.length > 0 && tab === "active" && (
                <span className="ml-1.5 px-1.5 py-0.5 rounded-full bg-white/20 text-[10px]">
                  {sessions.length}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <p className="text-sm text-steel">Loading…</p>
      ) : sessions.length === 0 ? (
        <div className="text-center py-20 text-steel text-sm">
          {tab === "active"
            ? "No vehicles currently parked. Add parking_entry / parking_exit cameras to start tracking."
            : "No sessions recorded yet."}
        </div>
      ) : (
        <div className="space-y-2">
          {sessions.map((s) => (
            <SessionRow
              key={s.id}
              session={s}
              isNew={newIds.has(s.id)}
              onClose={() => handleClose(s.id)}
              onMarkPaid={() => handleMarkPaid(s.id)}
              onWaive={() => handleWaive(s.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function SessionRow({
  session: s,
  isNew,
  onClose,
  onMarkPaid,
  onWaive,
}: {
  session: ParkingSession;
  isNew: boolean;
  onClose: () => void;
  onMarkPaid: () => void;
  onWaive: () => void;
}) {
  const isOpen = s.exit_event_id === null;
  const duration = useLiveDuration(isOpen ? s.entry_ts : null);

  const displayDuration = isOpen
    ? duration
    : s.duration_s !== null
    ? fmtDuration(s.duration_s)
    : "—";

  return (
    <div
      className={`flex items-center gap-4 p-3 rounded-lg border transition-all ${
        isNew
          ? "border-signal/60 bg-signal/5 animate-plate-pulse"
          : "border-hairline dark:border-hairline-dark bg-white dark:bg-ink/40"
      }`}
    >
      {/* Plate */}
      <div className="shrink-0 w-36">
        {s.plate_text ? (
          <PlateStrip plateText={s.plate_text} confidence={1} isNew={isNew} />
        ) : (
          <span className="text-xs text-steel font-mono">Unknown</span>
        )}
      </div>

      {/* Times */}
      <div className="flex-1 min-w-0 grid grid-cols-3 gap-2 text-xs">
        <div>
          <p className="text-steel">Entry</p>
          <p className="text-ink dark:text-bone font-medium truncate">
            {s.entry_ts ? formatTs(s.entry_ts) : "—"}
          </p>
        </div>
        <div>
          <p className="text-steel">Duration</p>
          <p className={`font-medium tabular-nums ${isOpen ? "text-signal" : "text-ink dark:text-bone"}`}>
            {displayDuration}
            {isOpen && <span className="ml-1 inline-block w-1.5 h-1.5 rounded-full bg-signal animate-pulse" />}
          </p>
        </div>
        <div>
          <p className="text-steel">Amount</p>
          <p className="text-ink dark:text-bone font-medium">
            {s.amount_due !== null ? `NPR ${s.amount_due.toFixed(0)}` : isOpen ? "…" : "—"}
          </p>
        </div>
      </div>

      {/* Status badge */}
      <div className="shrink-0">
        <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${PAYMENT_STYLES[s.payment_status]}`}>
          {s.payment_status}
        </span>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1.5 shrink-0">
        {isOpen && (
          <ActionBtn label="Close" onClick={onClose} />
        )}
        {!isOpen && s.payment_status === "pending" && s.amount_due !== null && s.amount_due > 0 && (
          <ActionBtn label="Mark paid" onClick={onMarkPaid} variant="confirm" />
        )}
        {s.payment_status === "pending" && (
          <ActionBtn label="Waive" onClick={onWaive} />
        )}
      </div>
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

function fmtDuration(secs: number): string {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}
