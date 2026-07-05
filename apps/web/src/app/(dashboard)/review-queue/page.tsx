"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/auth";
import { API_BASE } from "@/lib/api";

interface ReviewItem {
  id: string;
  site_id: string;
  camera_id: string;
  ts: string;
  snapshot_url: string | null;
  raw_text: string;
  raw_confidence: number;
  corrected_text: string | null;
  status: "pending" | "corrected" | "dismissed";
  reviewed_at: string | null;
  created_at: string;
}

async function fetchQueue(token: string, status: string): Promise<ReviewItem[]> {
  const res = await fetch(`${API_BASE}/review-queue?status=${status}&limit=50`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Failed to load review queue");
  return res.json();
}

async function patchItem(
  token: string,
  id: string,
  payload: { status: string; corrected_text?: string },
): Promise<ReviewItem> {
  const res = await fetch(`${API_BASE}/review-queue/${id}`, {
    method: "PATCH",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Update failed");
  }
  return res.json();
}

function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const colour =
    pct >= 65 ? "text-ok" : pct >= 50 ? "text-caution" : "text-alert";
  return (
    <span className={`text-xs font-mono font-semibold ${colour}`}>{pct}%</span>
  );
}

function ReviewCard({
  item,
  token,
  onDone,
}: {
  item: ReviewItem;
  token: string;
  onDone: () => void;
}) {
  const [correction, setCorrection] = useState(item.raw_text);
  const [error, setError] = useState<string | null>(null);
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: (payload: { status: string; corrected_text?: string }) =>
      patchItem(token, item.id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["review-queue"] });
      onDone();
    },
    onError: (e: Error) => setError(e.message),
  });

  function handleCorrect() {
    const cleaned = correction.toUpperCase().replace(/[^A-Z0-9]/g, "");
    if (cleaned.length < 3) {
      setError("Plate must be at least 3 characters");
      return;
    }
    setError(null);
    mutation.mutate({ status: "corrected", corrected_text: cleaned });
  }

  function handleDismiss() {
    setError(null);
    mutation.mutate({ status: "dismissed" });
  }

  const busy = mutation.isPending;

  return (
    <div className="rounded-[12px] border border-hairline dark:border-hairline-dark bg-white dark:bg-ink-soft overflow-hidden flex flex-col">
      {/* Crop image */}
      <div className="h-24 bg-hairline dark:bg-hairline-dark flex items-center justify-center">
        {item.snapshot_url ? (
          <img
            src={item.snapshot_url}
            alt={`Plate crop ${item.raw_text}`}
            className="h-full w-full object-contain"
          />
        ) : (
          <span className="text-xs text-steel">No image</span>
        )}
      </div>

      <div className="p-3 flex flex-col gap-2 flex-1">
        {/* Raw read */}
        <div className="flex items-center justify-between">
          <span className="font-mono text-sm font-bold text-ink dark:text-bone tracking-widest">
            {item.raw_text}
          </span>
          <ConfidenceBadge value={item.raw_confidence} />
        </div>

        <p className="text-xs text-steel">
          {new Date(item.ts).toLocaleString()} · cam {item.camera_id.slice(0, 8)}
        </p>

        {/* Correction input */}
        <input
          type="text"
          value={correction}
          onChange={(e) =>
            setCorrection(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ""))
          }
          maxLength={13}
          placeholder="Correct plate text"
          disabled={busy}
          className="w-full rounded-[4px] border border-hairline dark:border-hairline-dark bg-white dark:bg-ink px-2 py-1.5 text-sm font-mono text-ink dark:text-bone focus:outline-none focus:ring-1 focus:ring-signal uppercase tracking-wider"
        />

        {error && <p className="text-xs text-alert">{error}</p>}

        <div className="flex gap-2 mt-auto">
          <button
            onClick={handleCorrect}
            disabled={busy}
            className="flex-1 rounded-[4px] bg-signal text-white text-xs font-semibold py-1.5 hover:bg-signal/80 disabled:opacity-50 transition-colors"
          >
            Correct
          </button>
          <button
            onClick={handleDismiss}
            disabled={busy}
            className="flex-1 rounded-[4px] border border-hairline dark:border-hairline-dark text-steel text-xs py-1.5 hover:text-ink dark:hover:text-bone disabled:opacity-50 transition-colors"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ReviewQueuePage() {
  const { accessToken } = useAuthStore();
  const [tab, setTab] = useState<"pending" | "corrected" | "dismissed">("pending");
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const { data, isLoading, isError } = useQuery({
    queryKey: ["review-queue", tab],
    queryFn: () => fetchQueue(accessToken!, tab),
    enabled: !!accessToken,
    staleTime: 15_000,
    refetchInterval: 30_000,
  });

  const visible = (data ?? []).filter((item) => !dismissed.has(item.id));
  const pending = tab === "pending" ? visible : [];

  function tabs() {
    return (["pending", "corrected", "dismissed"] as const).map((t) => (
      <button
        key={t}
        onClick={() => setTab(t)}
        className={`px-3 py-1.5 text-sm rounded-[4px] transition-colors ${
          tab === t
            ? "bg-signal text-white font-semibold"
            : "text-steel hover:text-ink dark:hover:text-bone"
        }`}
      >
        {t.charAt(0).toUpperCase() + t.slice(1)}
      </button>
    ));
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-medium text-ink dark:text-bone">Review queue</h1>
          <p className="text-xs text-steel mt-0.5">
            Low-confidence OCR reads waiting for human correction. Corrections become model training data.
          </p>
        </div>
        {tab === "pending" && (
          <span className="text-sm text-steel">
            {visible.length} pending
          </span>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1">{tabs()}</div>

      {isLoading && (
        <p className="text-sm text-steel">Loading…</p>
      )}

      {isError && (
        <p className="text-sm text-alert">Failed to load review queue.</p>
      )}

      {!isLoading && !isError && visible.length === 0 && (
        <div className="rounded-[12px] border border-hairline dark:border-hairline-dark p-8 text-center">
          <p className="text-sm text-steel">
            {tab === "pending"
              ? "No pending items — all clear."
              : `No ${tab} items.`}
          </p>
        </div>
      )}

      {tab === "pending" && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {pending.map((item) => (
            <ReviewCard
              key={item.id}
              item={item}
              token={accessToken!}
              onDone={() => setDismissed((prev) => new Set([...prev, item.id]))}
            />
          ))}
        </div>
      )}

      {tab !== "pending" && (
        <div className="rounded-[12px] border border-hairline dark:border-hairline-dark overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline dark:border-hairline-dark bg-hairline/40 dark:bg-hairline-dark/40">
                <th className="text-left px-4 py-2 text-xs font-semibold text-steel">Raw</th>
                <th className="text-left px-4 py-2 text-xs font-semibold text-steel">Corrected</th>
                <th className="text-left px-4 py-2 text-xs font-semibold text-steel">Conf</th>
                <th className="text-left px-4 py-2 text-xs font-semibold text-steel">Reviewed at</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((item) => (
                <tr
                  key={item.id}
                  className="border-b border-hairline dark:border-hairline-dark last:border-0"
                >
                  <td className="px-4 py-2 font-mono text-ink dark:text-bone">{item.raw_text}</td>
                  <td className="px-4 py-2 font-mono text-ok">{item.corrected_text ?? "—"}</td>
                  <td className="px-4 py-2"><ConfidenceBadge value={item.raw_confidence} /></td>
                  <td className="px-4 py-2 text-xs text-steel">
                    {item.reviewed_at ? new Date(item.reviewed_at).toLocaleString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
