const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { token?: string } = {},
): Promise<T> {
  const { token, ...init } = options;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });

  if (!res.ok) {
    let code = "unknown_error";
    let message = res.statusText;
    try {
      const body = await res.json();
      code = body?.error?.code ?? code;
      message = body?.error?.message ?? message;
    } catch {}
    throw new ApiError(res.status, code, message);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export { ApiError };

export const api = {
  auth: {
    login: (email: string, password: string) =>
      request<{ access_token: string; refresh_token: string; token_type: string }>(
        "/auth/login",
        { method: "POST", body: JSON.stringify({ email, password }) },
      ),
    me: (token: string) =>
      request<{ id: string; email: string; name: string; role: string }>(
        "/auth/me",
        { token },
      ),
    logout: (token: string) =>
      request<void>("/auth/logout", { method: "POST", token }),
  },

  cameras: {
    list: (token: string, siteId?: string) =>
      request<Camera[]>(
        `/cameras${siteId ? `?site_id=${siteId}` : ""}`,
        { token },
      ),
    create: (token: string, body: CameraCreate) =>
      request<Camera>("/cameras", { method: "POST", body: JSON.stringify(body), token }),
    get: (token: string, id: string) =>
      request<Camera>(`/cameras/${id}`, { token }),
  },

  events: {
    list: (token: string, params: EventsParams = {}) => {
      const q = new URLSearchParams();
      if (params.siteId) q.set("site_id", params.siteId);
      if (params.cameraId) q.set("camera_id", params.cameraId);
      if (params.plate) q.set("plate", params.plate);
      if (params.from) q.set("from", params.from);
      if (params.to) q.set("to", params.to);
      if (params.limit) q.set("limit", String(params.limit));
      if (params.cursor) q.set("cursor", params.cursor);
      return request<EventsPage>(`/events?${q}`, { token });
    },
  },

  sites: {
    list: (token: string) => request<Site[]>("/sites", { token }),
    create: (token: string, body: SiteCreate) =>
      request<Site>("/sites", { method: "POST", body: JSON.stringify(body), token }),
  },

  watchlists: {
    list: (token: string, siteId?: string) =>
      request<Watchlist[]>(`/watchlists${siteId ? `?site_id=${siteId}` : ""}`, { token }),
    create: (token: string, body: WatchlistCreate) =>
      request<Watchlist>("/watchlists", { method: "POST", body: JSON.stringify(body), token }),
    delete: (token: string, id: string) =>
      request<void>(`/watchlists/${id}`, { method: "DELETE", token }),
    listEntries: (token: string, watchlistId: string) =>
      request<WatchlistEntry[]>(`/watchlists/${watchlistId}/entries`, { token }),
    addEntry: (token: string, watchlistId: string, body: EntryCreate) =>
      request<WatchlistEntry>(`/watchlists/${watchlistId}/entries`, {
        method: "POST",
        body: JSON.stringify(body),
        token,
      }),
    removeEntry: (token: string, watchlistId: string, entryId: string) =>
      request<void>(`/watchlists/${watchlistId}/entries/${entryId}`, {
        method: "DELETE",
        token,
      }),
  },

  alerts: {
    list: (token: string, params: AlertsParams = {}) => {
      const q = new URLSearchParams();
      if (params.siteId) q.set("site_id", params.siteId);
      if (params.status) q.set("status", params.status);
      if (params.limit) q.set("limit", String(params.limit));
      if (params.cursor) q.set("cursor", params.cursor);
      return request<AlertsPage>(`/alerts?${q}`, { token });
    },
    counts: (token: string, siteId?: string) =>
      request<AlertCounts>(`/alerts/counts${siteId ? `?site_id=${siteId}` : ""}`, { token }),
    ack: (token: string, id: string, notes?: string) =>
      request<Alert>(`/alerts/${id}/ack`, {
        method: "POST",
        body: JSON.stringify({ notes }),
        token,
      }),
    snooze: (token: string, id: string, snoozeUntil: string, notes?: string) =>
      request<Alert>(`/alerts/${id}/snooze`, {
        method: "POST",
        body: JSON.stringify({ snooze_until: snoozeUntil, notes }),
        token,
      }),
    resolve: (token: string, id: string, notes?: string) =>
      request<Alert>(`/alerts/${id}/resolve`, {
        method: "POST",
        body: JSON.stringify({ notes }),
        token,
      }),
  },
};

// ── Types ────────────────────────────────────────────────────────────────────

export interface Camera {
  id: string;
  site_id: string;
  name: string;
  kind: "ip" | "analog";
  stream_url: string | null;
  role: string;
  health_status: "online" | "offline" | "degraded" | "unknown";
  enabled: boolean;
  fps: number | null;
  resolution_w: number | null;
  resolution_h: number | null;
}

export interface CameraCreate {
  name: string;
  site_id: string;
  kind?: "ip" | "analog";
  stream_url?: string;
  role?: string;
}

export interface PlateOut {
  id: string;
  text: string;
  region: string | null;
  format_class: string;
}

export interface Event {
  id: string;
  site_id: string;
  camera_id: string;
  ts: string;
  kind: string;
  vehicle_id: string | null;
  plate_id: string | null;
  snapshot_key: string | null;
  clip_key: string | null;
  confidence: number | null;
  plate: PlateOut | null;
}

export interface EventsPage {
  items: Event[];
  next_cursor: string | null;
}

export interface EventsParams {
  siteId?: string;
  cameraId?: string;
  plate?: string;
  from?: string;
  to?: string;
  limit?: number;
  cursor?: string;
}

export interface Site {
  id: string;
  org_id: string;
  name: string;
  address: string | null;
  timezone: string;
  plate_region: string;
}

export interface SiteCreate {
  org_id: string;
  name: string;
  address?: string;
  timezone?: string;
  plate_region?: string;
}

export interface Watchlist {
  id: string;
  site_id: string;
  name: string;
  category: "blocked" | "vip" | "resident" | "vendor" | "staff" | "police_notice";
  alert_channels: string[];
}

export interface WatchlistCreate {
  site_id: string;
  name: string;
  category: Watchlist["category"];
  alert_channels?: string[];
}

export interface WatchlistEntry {
  id: string;
  watchlist_id: string;
  plate_text: string;
  plate_pattern: "exact" | "prefix" | "fuzzy";
  notes: string | null;
}

export interface EntryCreate {
  plate_text: string;
  plate_pattern?: "exact" | "prefix" | "fuzzy";
  notes?: string;
}

export type AlertStatus = "new" | "ack" | "snoozed" | "resolved";

export interface Alert {
  id: string;
  event_id: string;
  watchlist_id: string | null;
  status: AlertStatus;
  ack_by: string | null;
  ack_at: string | null;
  snooze_until: string | null;
  notes: string | null;
  created_at: string;
  plate_text: string | null;
  camera_id: string | null;
  site_id: string | null;
  watchlist_name: string | null;
}

export interface AlertsPage {
  items: Alert[];
  total: number;
  next_cursor: string | null;
}

export interface AlertsParams {
  siteId?: string;
  status?: AlertStatus;
  limit?: number;
  cursor?: string;
}

export interface AlertCounts {
  new: number;
  ack: number;
  snoozed: number;
  resolved: number;
  total_new: number;
}
