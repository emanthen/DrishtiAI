"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/auth";
import { api, type CameraCreate, API_BASE } from "@/lib/api";

interface LiveStatus {
  camera_id: string;
  online: boolean;
  fps: number;
  frames: number;
  last_seen_s: number | null;
}

async function fetchLiveStatus(token: string): Promise<LiveStatus[]> {
  const res = await fetch(`${API_BASE}/cameras/live-status`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return [];
  return res.json();
}

export default function CamerasPage() {
  const { accessToken } = useAuthStore();
  const queryClient = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);

  const { data: cameras, isLoading } = useQuery({
    queryKey: ["cameras"],
    queryFn: () => api.cameras.list(accessToken!),
    enabled: !!accessToken,
    refetchInterval: 10_000,
  });

  const { data: liveMap } = useQuery({
    queryKey: ["cameras-live"],
    queryFn: async () => {
      const list = await fetchLiveStatus(accessToken!);
      return Object.fromEntries(list.map((s) => [s.camera_id, s]));
    },
    enabled: !!accessToken,
    refetchInterval: 5_000,
  });

  const addMutation = useMutation({
    mutationFn: (body: CameraCreate) => api.cameras.create(accessToken!, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cameras"] });
      setShowAdd(false);
    },
  });

  const offlineCount = cameras?.filter((c) => c.health_status === "offline").length ?? 0;

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-medium text-ink dark:text-bone">Cameras</h1>
          {offlineCount > 0 && (
            <p className="text-xs text-alert mt-0.5 font-semibold">
              ⚠ {offlineCount} camera{offlineCount > 1 ? "s" : ""} offline
            </p>
          )}
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="rounded-[8px] bg-signal px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 transition-opacity"
        >
          Add camera
        </button>
      </div>

      {isLoading && <p className="text-sm text-steel">Loading cameras…</p>}

      <div className="rounded-[12px] border border-hairline dark:border-hairline-dark overflow-hidden">
        {cameras && cameras.length > 0 ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline dark:border-hairline-dark bg-bone dark:bg-ink">
                <th className="py-2 px-3 text-left text-xs font-medium text-steel w-8"></th>
                <th className="py-2 px-3 text-left text-xs font-medium text-steel">Name</th>
                <th className="py-2 px-3 text-left text-xs font-medium text-steel">Role</th>
                <th className="py-2 px-3 text-left text-xs font-medium text-steel">Status</th>
                <th className="py-2 px-3 text-left text-xs font-medium text-steel">FPS</th>
                <th className="py-2 px-3 text-left text-xs font-medium text-steel">Last seen</th>
                <th className="py-2 px-3 text-left text-xs font-medium text-steel">Stream URL</th>
              </tr>
            </thead>
            <tbody>
              {cameras.map((cam) => {
                const live = liveMap?.[cam.id];
                const effectiveStatus = live
                  ? live.online ? "online" : "offline"
                  : cam.health_status;
                return (
                  <tr
                    key={cam.id}
                    className="border-b border-hairline dark:border-hairline-dark last:border-0 hover:bg-hairline/20 dark:hover:bg-hairline-dark/20 transition-colors"
                  >
                    <td className="py-2 px-3">
                      <LiveDot status={effectiveStatus} />
                    </td>
                    <td className="py-2 px-3 font-medium text-ink dark:text-bone">{cam.name}</td>
                    <td className="py-2 px-3 text-steel">{cam.role}</td>
                    <td className="py-2 px-3">
                      <StatusChip status={effectiveStatus} />
                    </td>
                    <td className="py-2 px-3 text-steel tabular-nums">
                      {live ? `${live.fps.toFixed(1)}` : "—"}
                    </td>
                    <td className="py-2 px-3 text-steel tabular-nums text-xs">
                      {live?.last_seen_s != null ? `${live.last_seen_s}s ago` : "—"}
                    </td>
                    <td className="py-2 px-3 font-mono text-xs text-steel truncate max-w-xs">
                      {cam.stream_url ?? "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          !isLoading && (
            <div className="py-10 text-center">
              <p className="text-sm text-ink dark:text-bone">No cameras added yet.</p>
              <p className="mt-1 text-xs text-steel">Add an IP camera or analog stream to get started.</p>
            </div>
          )
        )}
      </div>

      {showAdd && (
        <AddCameraModal
          onSubmit={(v) => addMutation.mutate(v)}
          onClose={() => setShowAdd(false)}
          error={addMutation.error?.message}
        />
      )}
    </div>
  );
}

function LiveDot({ status }: { status: string }) {
  if (status === "online") {
    return (
      <span className="relative flex h-2.5 w-2.5">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-confirm opacity-75" />
        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-confirm" />
      </span>
    );
  }
  const color =
    status === "offline" ? "bg-alert" :
    status === "degraded" ? "bg-yellow-500" : "bg-steel";
  return <span className={`inline-flex rounded-full h-2.5 w-2.5 ${color}`} />;
}

function StatusChip({ status }: { status: string }) {
  const map: Record<string, string> = {
    online: "text-confirm",
    offline: "text-alert",
    degraded: "text-yellow-600",
    unknown: "text-steel",
  };
  return <span className={`text-xs font-medium ${map[status] ?? "text-steel"}`}>{status}</span>;
}

function AddCameraModal({
  onSubmit,
  onClose,
  error,
}: {
  onSubmit: (v: CameraCreate) => void;
  onClose: () => void;
  error?: string;
}) {
  const [name, setName] = useState("");
  const [streamUrl, setStreamUrl] = useState("");
  const [siteId, setSiteId] = useState("");
  const [role, setRole] = useState("anpr_lane");

  return (
    <div className="fixed inset-0 bg-ink/60 flex items-center justify-center z-50 p-4">
      <div className="bg-bone dark:bg-ink rounded-[12px] border border-hairline dark:border-hairline-dark p-6 w-full max-w-md">
        <h2 className="text-base font-medium text-ink dark:text-bone mb-4">Add camera</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            onSubmit({ name, stream_url: streamUrl, site_id: siteId, role });
          }}
          className="space-y-3"
        >
          <Field label="Name" value={name} onChange={setName} required />
          <Field label="Site ID" value={siteId} onChange={setSiteId} placeholder="UUID" required />
          <Field label="Stream URL" value={streamUrl} onChange={setStreamUrl} placeholder="rtsp://..." />
          <div>
            <label className="block text-xs font-medium text-steel mb-1">Role</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full rounded-[4px] border border-hairline dark:border-hairline-dark bg-white dark:bg-ink px-3 py-2 text-sm text-ink dark:text-bone"
            >
              <option value="anpr_lane">ANPR lane (full pipeline)</option>
              <option value="parking_entry">Parking entry</option>
              <option value="parking_exit">Parking exit</option>
              <option value="parking">Parking (bidirectional)</option>
              <option value="perimeter">Perimeter</option>
              <option value="general">General</option>
            </select>
          </div>
          {error && <p className="text-xs text-alert">{error}</p>}
          <div className="flex gap-2 pt-2">
            <button
              type="submit"
              className="flex-1 rounded-[8px] bg-signal px-3 py-2 text-sm font-medium text-white hover:opacity-90"
            >
              Add camera
            </button>
            <button
              type="button"
              onClick={onClose}
              className="flex-1 rounded-[8px] border border-hairline dark:border-hairline-dark px-3 py-2 text-sm text-steel hover:text-ink dark:hover:text-bone"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, placeholder, required }: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  required?: boolean;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-steel mb-1">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        className="w-full rounded-[4px] border border-hairline dark:border-hairline-dark bg-white dark:bg-ink px-3 py-2 text-sm text-ink dark:text-bone focus:outline-none focus:ring-1 focus:ring-signal"
      />
    </div>
  );
}
