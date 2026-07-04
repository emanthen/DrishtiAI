"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/store/auth";
import { API_BASE } from "@/lib/api";

type WebhookEvent =
  | "plate_read" | "alert_new" | "alert_resolved"
  | "gate_trigger" | "camera_offline" | "parking_open" | "parking_close";

const ALL_EVENTS: WebhookEvent[] = [
  "plate_read", "alert_new", "alert_resolved",
  "gate_trigger", "camera_offline", "parking_open", "parking_close",
];

interface Webhook {
  id: string;
  site_id: string;
  name: string;
  url: string;
  has_secret: boolean;
  events: string[];
  enabled: boolean;
  created_at: string;
  last_triggered_at: string | null;
  last_status_code: number | null;
}

interface TestResult {
  url: string;
  status_code: number | null;
  ok: boolean;
  error: string | null;
}

async function apiFetch<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(init?.headers ?? {}) },
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  if (res.status === 204) return undefined as T;
  return res.json();
}

export default function WebhooksPage() {
  const { accessToken } = useAuthStore();
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [loading, setLoading] = useState(true);
  const [testResults, setTestResults] = useState<Record<string, TestResult>>({});
  const [testing, setTesting] = useState<string | null>(null);

  // Create form state
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newUrl, setNewUrl] = useState("");
  const [newSecret, setNewSecret] = useState("");
  const [newSiteId, setNewSiteId] = useState("");
  const [newEvents, setNewEvents] = useState<WebhookEvent[]>([]);
  const [saving, setSaving] = useState(false);
  const [createError, setCreateError] = useState("");

  useEffect(() => {
    if (!accessToken) return;
    apiFetch<Webhook[]>("/webhooks", accessToken)
      .then(setWebhooks)
      .finally(() => setLoading(false));
  }, [accessToken]);

  async function toggleEnabled(wh: Webhook) {
    if (!accessToken) return;
    const updated = await apiFetch<Webhook>(`/webhooks/${wh.id}`, accessToken, {
      method: "PATCH",
      body: JSON.stringify({ enabled: !wh.enabled }),
    });
    setWebhooks((prev) => prev.map((w) => (w.id === wh.id ? updated : w)));
  }

  async function deleteWebhook(id: string) {
    if (!accessToken || !confirm("Delete this webhook?")) return;
    await apiFetch<undefined>(`/webhooks/${id}`, accessToken, { method: "DELETE" });
    setWebhooks((prev) => prev.filter((w) => w.id !== id));
  }

  async function testWebhook(id: string) {
    if (!accessToken) return;
    setTesting(id);
    try {
      const result = await apiFetch<TestResult>(`/webhooks/${id}/test`, accessToken, { method: "POST" });
      setTestResults((prev) => ({ ...prev, [id]: result }));
    } catch (e: any) {
      setTestResults((prev) => ({ ...prev, [id]: { url: "", status_code: null, ok: false, error: e.message } }));
    } finally {
      setTesting(null);
    }
  }

  async function createWebhook(e: React.FormEvent) {
    e.preventDefault();
    if (!accessToken) return;
    setCreateError("");
    setSaving(true);
    try {
      const created = await apiFetch<Webhook>("/webhooks", accessToken, {
        method: "POST",
        body: JSON.stringify({
          site_id: newSiteId,
          name: newName,
          url: newUrl,
          secret: newSecret || null,
          events: newEvents,
        }),
      });
      setWebhooks((prev) => [...prev, created]);
      setShowCreate(false);
      setNewName(""); setNewUrl(""); setNewSecret(""); setNewSiteId(""); setNewEvents([]);
    } catch (err: any) {
      setCreateError(err.message);
    } finally {
      setSaving(false);
    }
  }

  function toggleEvent(ev: WebhookEvent) {
    setNewEvents((prev) =>
      prev.includes(ev) ? prev.filter((e) => e !== ev) : [...prev, ev]
    );
  }

  const statusBadge = (code: number | null, ok: boolean) => {
    if (code === null) return <span className="text-xs text-alert">network error</span>;
    return (
      <span className={`text-xs font-mono ${ok ? "text-confirm" : "text-alert"}`}>
        HTTP {code}
      </span>
    );
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-ink dark:text-bone">Webhooks</h1>
          <p className="text-sm text-steel mt-0.5">
            Receive real-time HTTP POST callbacks when events occur.
          </p>
        </div>
        <button
          onClick={() => setShowCreate((v) => !v)}
          className="px-3 py-1.5 text-sm bg-signal text-white rounded hover:bg-signal/90 transition-colors"
        >
          {showCreate ? "Cancel" : "+ Add webhook"}
        </button>
      </div>

      {showCreate && (
        <form onSubmit={createWebhook} className="mb-6 p-4 border border-hairline dark:border-hairline-dark rounded-lg bg-white dark:bg-ink/60">
          <h2 className="text-sm font-semibold mb-4 text-ink dark:text-bone">New webhook</h2>
          {createError && (
            <p className="text-xs text-alert mb-3 bg-alert/10 px-3 py-2 rounded">{createError}</p>
          )}
          <div className="grid grid-cols-2 gap-4">
            <label className="flex flex-col gap-1">
              <span className="text-xs text-steel">Name</span>
              <input
                required value={newName} onChange={(e) => setNewName(e.target.value)}
                className="input-base text-sm" placeholder="My integration"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-steel">Site ID</span>
              <input
                required value={newSiteId} onChange={(e) => setNewSiteId(e.target.value)}
                className="input-base text-sm font-mono" placeholder="uuid"
              />
            </label>
            <label className="col-span-2 flex flex-col gap-1">
              <span className="text-xs text-steel">URL</span>
              <input
                required type="url" value={newUrl} onChange={(e) => setNewUrl(e.target.value)}
                className="input-base text-sm" placeholder="https://your-server.example.com/drishti"
              />
            </label>
            <label className="col-span-2 flex flex-col gap-1">
              <span className="text-xs text-steel">Signing secret (optional — HMAC-SHA256)</span>
              <input
                value={newSecret} onChange={(e) => setNewSecret(e.target.value)}
                className="input-base text-sm font-mono" placeholder="Leave blank for unsigned payloads"
              />
            </label>
          </div>

          <div className="mt-4">
            <p className="text-xs text-steel mb-2">Subscribe to events (empty = all):</p>
            <div className="flex flex-wrap gap-2">
              {ALL_EVENTS.map((ev) => (
                <button
                  key={ev} type="button"
                  onClick={() => toggleEvent(ev)}
                  className={`px-2 py-0.5 text-xs rounded border transition-colors ${
                    newEvents.includes(ev)
                      ? "border-signal bg-signal/10 text-signal"
                      : "border-hairline text-steel hover:border-signal"
                  }`}
                >
                  {ev}
                </button>
              ))}
            </div>
          </div>

          <button
            type="submit" disabled={saving}
            className="mt-4 px-4 py-1.5 text-sm bg-signal text-white rounded hover:bg-signal/90 disabled:opacity-50"
          >
            {saving ? "Creating…" : "Create webhook"}
          </button>
        </form>
      )}

      {loading ? (
        <p className="text-sm text-steel">Loading…</p>
      ) : webhooks.length === 0 ? (
        <p className="text-sm text-steel">No webhooks configured. Add one to start receiving callbacks.</p>
      ) : (
        <div className="space-y-3">
          {webhooks.map((wh) => (
            <div key={wh.id} className="border border-hairline dark:border-hairline-dark rounded-lg p-4 bg-white dark:bg-ink/60">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-ink dark:text-bone">{wh.name}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded-full ${wh.enabled ? "bg-confirm/15 text-confirm" : "bg-steel/15 text-steel"}`}>
                      {wh.enabled ? "enabled" : "disabled"}
                    </span>
                    {wh.has_secret && (
                      <span className="text-xs px-1.5 py-0.5 rounded-full bg-signal/15 text-signal">signed</span>
                    )}
                  </div>
                  <p className="text-xs font-mono text-steel mt-0.5 truncate">{wh.url}</p>
                  {wh.events.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {wh.events.map((ev) => (
                        <span key={ev} className="text-xs bg-hairline dark:bg-hairline-dark px-1.5 py-0.5 rounded text-steel">{ev}</span>
                      ))}
                    </div>
                  )}
                  {wh.last_triggered_at && (
                    <p className="text-xs text-steel mt-1.5">
                      Last triggered: {new Date(wh.last_triggered_at).toLocaleString()}
                      {wh.last_status_code !== null && (
                        <span className={`ml-2 font-mono ${wh.last_status_code < 300 ? "text-confirm" : "text-alert"}`}>
                          HTTP {wh.last_status_code}
                        </span>
                      )}
                    </p>
                  )}
                  {testResults[wh.id] && (
                    <p className="text-xs mt-1 flex items-center gap-1.5">
                      <span className="text-steel">Test result:</span>
                      {statusBadge(testResults[wh.id].status_code, testResults[wh.id].ok)}
                      {testResults[wh.id].error && (
                        <span className="text-alert">{testResults[wh.id].error}</span>
                      )}
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => testWebhook(wh.id)}
                    disabled={testing === wh.id}
                    className="px-2 py-1 text-xs border border-hairline dark:border-hairline-dark rounded hover:border-signal text-steel hover:text-signal transition-colors disabled:opacity-50"
                  >
                    {testing === wh.id ? "Testing…" : "Test"}
                  </button>
                  <button
                    onClick={() => toggleEnabled(wh)}
                    className="px-2 py-1 text-xs border border-hairline dark:border-hairline-dark rounded hover:border-signal text-steel hover:text-signal transition-colors"
                  >
                    {wh.enabled ? "Disable" : "Enable"}
                  </button>
                  <button
                    onClick={() => deleteWebhook(wh.id)}
                    className="px-2 py-1 text-xs border border-alert/30 rounded hover:border-alert text-alert/70 hover:text-alert transition-colors"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
