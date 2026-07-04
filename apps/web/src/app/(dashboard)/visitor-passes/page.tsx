"use client";

import { useEffect, useState, useCallback } from "react";
import { useAuthStore } from "@/store/auth";
import { api, VisitorPass } from "@/lib/api";
import { formatTs, relativeTime } from "@/lib/utils";
import { PlateStrip } from "@/components/ui/plate-strip";

type PassStatus = "active" | "upcoming" | "expired" | "used" | "all";

const STATUS_STYLES: Record<string, string> = {
  active:   "bg-confirm/15 text-confirm border border-confirm/30",
  upcoming: "bg-signal/15 text-signal border border-signal/30",
  expired:  "bg-steel/15 text-steel border border-steel/30",
  used:     "bg-steel/15 text-steel border border-steel/30",
};

const STATUS_TABS: Array<{ key: PassStatus; label: string }> = [
  { key: "active",   label: "Active" },
  { key: "upcoming", label: "Upcoming" },
  { key: "expired",  label: "Expired" },
  { key: "used",     label: "Used" },
  { key: "all",      label: "All" },
];

const DEFAULT_FORM = {
  plate: "",
  valid_from: "",
  valid_to: "",
  single_use: true,
  notes: "",
};

export default function VisitorPassesPage() {
  const { accessToken } = useAuthStore();
  const [tab, setTab] = useState<PassStatus>("active");
  const [passes, setPasses] = useState<VisitorPass[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Pre-fill valid_from to now and valid_to to +24h whenever form opens
  useEffect(() => {
    if (!showForm) return;
    const now = new Date();
    const plus24 = new Date(now.getTime() + 24 * 3600 * 1000);
    setForm((f) => ({
      ...f,
      valid_from: toLocalInput(now),
      valid_to: toLocalInput(plus24),
    }));
  }, [showForm]);

  const fetchPasses = useCallback(async () => {
    if (!accessToken) return;
    try {
      const result = await api.visitorPasses.list(accessToken, {
        status: tab === "all" ? undefined : tab,
        limit: 100,
      });
      setPasses(result.items);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [accessToken, tab]);

  useEffect(() => {
    setLoading(true);
    fetchPasses();
  }, [fetchPasses]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!accessToken) return;
    setFormError(null);
    if (!form.plate.trim()) { setFormError("Plate number is required"); return; }
    if (!form.valid_from || !form.valid_to) { setFormError("Both dates are required"); return; }

    setSubmitting(true);
    try {
      await api.visitorPasses.create(accessToken, {
        plate: form.plate.trim(),
        valid_from: new Date(form.valid_from).toISOString(),
        valid_to: new Date(form.valid_to).toISOString(),
        single_use: form.single_use,
        notes: form.notes || undefined,
      });
      setShowForm(false);
      setForm(DEFAULT_FORM);
      fetchPasses();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Failed to create pass");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCancel(id: string) {
    if (!accessToken || !confirm("Cancel this visitor pass?")) return;
    await api.visitorPasses.cancel(accessToken, id);
    fetchPasses();
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-medium text-ink dark:text-bone">Visitor Passes</h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="px-3 py-1.5 rounded bg-signal text-white text-sm font-medium hover:bg-signal/90 transition-colors"
        >
          {showForm ? "Cancel" : "+ Add pass"}
        </button>
      </div>

      {/* Add pass form */}
      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="mb-6 p-4 rounded-lg border border-signal/30 bg-signal/5 space-y-4"
        >
          <h2 className="text-sm font-medium text-ink dark:text-bone">New visitor pass</h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-steel mb-1">Plate number</label>
              <input
                value={form.plate}
                onChange={(e) => setForm((f) => ({ ...f, plate: e.target.value.toUpperCase() }))}
                placeholder="BA1PA1234"
                className="w-full px-3 py-1.5 rounded border border-hairline dark:border-hairline-dark bg-white dark:bg-ink text-sm font-mono text-ink dark:text-bone focus:outline-none focus:ring-1 focus:ring-signal"
              />
            </div>

            <div className="flex items-end gap-3">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.single_use}
                  onChange={(e) => setForm((f) => ({ ...f, single_use: e.target.checked }))}
                  className="w-4 h-4 accent-signal"
                />
                <span className="text-xs text-ink dark:text-bone">Single-use</span>
              </label>
              <span className="text-[11px] text-steel">
                {form.single_use ? "Gate opens once, then pass is consumed" : "Valid for multiple entries"}
              </span>
            </div>

            <div>
              <label className="block text-xs text-steel mb-1">Valid from</label>
              <input
                type="datetime-local"
                value={form.valid_from}
                onChange={(e) => setForm((f) => ({ ...f, valid_from: e.target.value }))}
                className="w-full px-3 py-1.5 rounded border border-hairline dark:border-hairline-dark bg-white dark:bg-ink text-sm text-ink dark:text-bone focus:outline-none focus:ring-1 focus:ring-signal"
              />
            </div>

            <div>
              <label className="block text-xs text-steel mb-1">Valid until</label>
              <input
                type="datetime-local"
                value={form.valid_to}
                onChange={(e) => setForm((f) => ({ ...f, valid_to: e.target.value }))}
                className="w-full px-3 py-1.5 rounded border border-hairline dark:border-hairline-dark bg-white dark:bg-ink text-sm text-ink dark:text-bone focus:outline-none focus:ring-1 focus:ring-signal"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs text-steel mb-1">Notes (optional)</label>
            <input
              value={form.notes}
              onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
              placeholder="Guest name, purpose, etc."
              className="w-full px-3 py-1.5 rounded border border-hairline dark:border-hairline-dark bg-white dark:bg-ink text-sm text-ink dark:text-bone focus:outline-none focus:ring-1 focus:ring-signal"
            />
          </div>

          {formError && <p className="text-xs text-alert">{formError}</p>}

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-1.5 rounded bg-signal text-white text-sm font-medium disabled:opacity-50"
            >
              {submitting ? "Creating…" : "Create pass"}
            </button>
            <button
              type="button"
              onClick={() => { setShowForm(false); setFormError(null); }}
              className="px-4 py-1.5 rounded bg-steel/10 text-steel text-sm font-medium hover:bg-steel/20"
            >
              Discard
            </button>
          </div>
        </form>
      )}

      {/* Status tabs */}
      <div className="flex gap-1 mb-4">
        {STATUS_TABS.map(({ key, label }) => (
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
          </button>
        ))}
      </div>

      {/* List */}
      {loading ? (
        <p className="text-sm text-steel">Loading…</p>
      ) : passes.length === 0 ? (
        <div className="text-center py-20 text-steel text-sm">
          {tab === "active"
            ? "No active passes. Add one with \"+ Add pass\"."
            : `No ${tab} passes.`}
        </div>
      ) : (
        <div className="space-y-2">
          {passes.map((p) => (
            <PassRow key={p.id} pass={p} onCancel={() => handleCancel(p.id)} />
          ))}
        </div>
      )}
    </div>
  );
}

function PassRow({ pass: p, onCancel }: { pass: VisitorPass; onCancel: () => void }) {
  const canCancel = p.pass_status !== "used" && p.pass_status !== "expired";

  return (
    <div className="flex items-center gap-4 p-3 rounded-lg border border-hairline dark:border-hairline-dark bg-white dark:bg-ink/40">
      {/* Plate */}
      <div className="shrink-0 w-36">
        <PlateStrip plateText={p.plate} confidence={1} isNew={false} />
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0 grid grid-cols-3 gap-2 text-xs">
        <div>
          <p className="text-steel">Valid from</p>
          <p className="text-ink dark:text-bone font-medium">{formatTs(p.valid_from)}</p>
        </div>
        <div>
          <p className="text-steel">Valid until</p>
          <p className="text-ink dark:text-bone font-medium">{formatTs(p.valid_to)}</p>
        </div>
        <div>
          <p className="text-steel">Type</p>
          <p className="text-ink dark:text-bone font-medium">
            {p.single_use ? "Single-use" : "Multi-use"}
          </p>
        </div>
      </div>

      {/* Notes */}
      {p.notes && (
        <p className="text-[11px] text-steel max-w-[120px] truncate shrink-0" title={p.notes}>
          {p.notes}
        </p>
      )}

      {/* Status */}
      <span className={`px-2 py-0.5 rounded text-[11px] font-medium shrink-0 ${STATUS_STYLES[p.pass_status] ?? ""}`}>
        {p.pass_status}
      </span>

      {/* Cancel */}
      {canCancel && (
        <button
          onClick={onCancel}
          className="px-2 py-1 rounded text-[11px] font-medium bg-alert/10 text-alert hover:bg-alert/20 transition-colors shrink-0"
        >
          Cancel
        </button>
      )}
    </div>
  );
}

function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
