"use client";

import { useEffect, useState, useCallback } from "react";
import { useAuthStore } from "@/store/auth";
import { api, GateController, GateRule, GateTriggerLog } from "@/lib/api";
import { formatTs, relativeTime } from "@/lib/utils";

const CONDITION_LABELS: Record<string, string> = {
  any_plate: "Any plate",
  watchlist_match: "Watchlist match",
  permit_valid: "Valid permit",
};

const TRIGGER_CONDITION_OPTIONS = [
  { value: "any_plate", label: "Any plate (always open)" },
  { value: "watchlist_match", label: "Watchlist match" },
  { value: "permit_valid", label: "Valid permit" },
] as const;

export default function GatesPage() {
  const { accessToken } = useAuthStore();
  const [controllers, setControllers] = useState<GateController[]>([]);
  const [selected, setSelected] = useState<GateController | null>(null);
  const [rules, setRules] = useState<GateRule[]>([]);
  const [log, setLog] = useState<GateTriggerLog[]>([]);
  const [triggering, setTriggering] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchControllers = useCallback(async () => {
    if (!accessToken) return;
    const list = await api.gates.listControllers(accessToken);
    setControllers(list);
    if (list.length > 0 && selected === null) setSelected(list[0]);
    setLoading(false);
  }, [accessToken, selected]);

  const fetchDetail = useCallback(async (ctrl: GateController) => {
    if (!accessToken) return;
    const [r, l] = await Promise.all([
      api.gates.listRules(accessToken, { controllerId: ctrl.id }),
      api.gates.controllerLog(accessToken, ctrl.id, 20),
    ]);
    setRules(r);
    setLog(l);
  }, [accessToken]);

  useEffect(() => { fetchControllers(); }, [fetchControllers]);
  useEffect(() => { if (selected) fetchDetail(selected); }, [selected, fetchDetail]);

  async function handleTrigger(ctrl: GateController) {
    if (!accessToken) return;
    setTriggering(ctrl.id);
    try {
      await api.gates.trigger(accessToken, ctrl.id);
      if (selected?.id === ctrl.id) fetchDetail(ctrl);
    } catch (err: unknown) {
      alert(`Trigger failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setTriggering(null);
    }
  }

  async function handleToggleRule(rule: GateRule) {
    if (!accessToken) return;
    await api.gates.patchRule(accessToken, rule.id, { enabled: !rule.enabled });
    if (selected) fetchDetail(selected);
  }

  async function handleDeleteRule(rule: GateRule) {
    if (!accessToken || !confirm("Delete this rule?")) return;
    await api.gates.deleteRule(accessToken, rule.id);
    if (selected) fetchDetail(selected);
  }

  if (loading) return <div className="p-6 text-sm text-steel">Loading…</div>;

  return (
    <div className="flex h-full">
      {/* Left panel — controller list */}
      <aside className="w-64 shrink-0 border-r border-hairline dark:border-hairline-dark flex flex-col">
        <div className="px-4 py-3 border-b border-hairline dark:border-hairline-dark">
          <h1 className="text-sm font-medium text-ink dark:text-bone">Gate Controllers</h1>
        </div>
        <div className="flex-1 overflow-y-auto py-1">
          {controllers.length === 0 ? (
            <p className="px-4 py-8 text-xs text-steel text-center">
              No gate controllers configured.
            </p>
          ) : (
            controllers.map((ctrl) => (
              <button
                key={ctrl.id}
                onClick={() => setSelected(ctrl)}
                className={`w-full text-left px-4 py-3 transition-colors ${
                  selected?.id === ctrl.id
                    ? "bg-signal/10 border-r-2 border-signal"
                    : "hover:bg-hairline dark:hover:bg-hairline-dark"
                }`}
              >
                <p className="text-sm font-medium text-ink dark:text-bone truncate">{ctrl.name}</p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className="text-[10px] text-steel uppercase tracking-wide">{ctrl.kind}</span>
                  <span className={`w-1.5 h-1.5 rounded-full ${ctrl.enabled ? "bg-confirm" : "bg-steel"}`} />
                </div>
              </button>
            ))
          )}
        </div>
      </aside>

      {/* Right panel — rules + log */}
      {selected ? (
        <main className="flex-1 overflow-y-auto p-6 space-y-8">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-medium text-ink dark:text-bone">{selected.name}</h2>
              <p className="text-xs text-steel mt-0.5">
                {selected.kind} · pulse {selected.open_pulse_ms} ms · {selected.enabled ? "enabled" : "disabled"}
              </p>
            </div>
            <button
              onClick={() => handleTrigger(selected)}
              disabled={!selected.enabled || triggering === selected.id}
              className="px-4 py-2 rounded bg-signal text-white text-sm font-medium disabled:opacity-40 hover:bg-signal/90 transition-colors"
            >
              {triggering === selected.id ? "Opening…" : "Open gate"}
            </button>
          </div>

          {/* Rules */}
          <section>
            <h3 className="text-xs font-medium text-steel uppercase tracking-wider mb-3">
              Trigger rules
            </h3>
            {rules.length === 0 ? (
              <p className="text-sm text-steel py-4">
                No rules. Add a rule so plates auto-trigger this gate.
              </p>
            ) : (
              <div className="space-y-2">
                {rules.map((rule) => (
                  <RuleRow
                    key={rule.id}
                    rule={rule}
                    onToggle={() => handleToggleRule(rule)}
                    onDelete={() => handleDeleteRule(rule)}
                  />
                ))}
              </div>
            )}
          </section>

          {/* Recent trigger log */}
          <section>
            <h3 className="text-xs font-medium text-steel uppercase tracking-wider mb-3">
              Recent activity
            </h3>
            {log.length === 0 ? (
              <p className="text-sm text-steel py-4">No triggers recorded yet.</p>
            ) : (
              <div className="space-y-1.5">
                {log.map((entry) => (
                  <LogRow key={entry.id} entry={entry} />
                ))}
              </div>
            )}
          </section>
        </main>
      ) : (
        <main className="flex-1 flex items-center justify-center text-sm text-steel">
          Select a controller to manage it.
        </main>
      )}
    </div>
  );
}

function RuleRow({
  rule,
  onToggle,
  onDelete,
}: {
  rule: GateRule;
  onToggle: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg border border-hairline dark:border-hairline-dark bg-white dark:bg-ink/40">
      <div className="flex-1 min-w-0">
        <p className="text-sm text-ink dark:text-bone font-medium">
          {CONDITION_LABELS[rule.trigger_on] ?? rule.trigger_on}
        </p>
        <p className="text-[11px] text-steel mt-0.5">priority {rule.priority}</p>
      </div>
      <button
        onClick={onToggle}
        className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
          rule.enabled
            ? "bg-confirm/15 text-confirm"
            : "bg-steel/10 text-steel"
        }`}
      >
        {rule.enabled ? "Enabled" : "Disabled"}
      </button>
      <button
        onClick={onDelete}
        className="px-2 py-0.5 rounded text-[11px] font-medium bg-alert/10 text-alert hover:bg-alert/20 transition-colors"
      >
        Delete
      </button>
    </div>
  );
}

function LogRow({ entry }: { entry: GateTriggerLog }) {
  return (
    <div className="flex items-center gap-3 px-3 py-2 rounded border border-hairline dark:border-hairline-dark text-xs">
      <span className={`w-2 h-2 rounded-full shrink-0 ${entry.success ? "bg-confirm" : "bg-alert"}`} />
      <span className="font-mono text-ink dark:text-bone w-28 shrink-0">
        {entry.plate_text ?? "manual"}
      </span>
      <span className="text-steel flex-1 truncate">
        {entry.success ? "Gate opened" : entry.error_msg ?? "Failed"}
      </span>
      <span className="text-steel shrink-0" title={formatTs(entry.triggered_at)}>
        {relativeTime(entry.triggered_at)}
      </span>
    </div>
  );
}
