export const API_BASE =
  process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { token?: string } = {}
): Promise<T> {
  const { token, ...init } = options;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = body?.detail ?? msg;
    } catch {}
    throw new ApiError(res.status, msg);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export { ApiError };

export const api = {
  auth: {
    login: (email: string, password: string) =>
      request<{ access_token: string; refresh_token: string }>(
        "/auth/login",
        { method: "POST", body: JSON.stringify({ email, password }) }
      ),
    me: (token: string) =>
      request<{ id: string; email: string; name: string; role: string }>(
        "/auth/me",
        { token }
      ),
    logout: (token: string) =>
      request<void>("/auth/logout", { method: "POST", token }),
  },

  analytics: {
    overview: (token: string) =>
      request<AnalyticsOverview>("/analytics/overview", { token }),
  },

  alerts: {
    list: (token: string, params: { status?: string; limit?: number } = {}) => {
      const q = new URLSearchParams();
      if (params.status) q.set("status", params.status);
      if (params.limit) q.set("limit", String(params.limit));
      return request<AlertsPage>(`/alerts?${q}`, { token });
    },
    ack: (token: string, id: string) =>
      request<Alert>(`/alerts/${id}/ack`, { method: "POST", body: "{}", token }),
    resolve: (token: string, id: string) =>
      request<Alert>(`/alerts/${id}/resolve`, { method: "POST", body: "{}", token }),
    snooze: (token: string, id: string, until: string) =>
      request<Alert>(`/alerts/${id}/snooze`, {
        method: "POST",
        body: JSON.stringify({ snooze_until: until }),
        token,
      }),
  },

  visitorPasses: {
    mine: (token: string, status?: string) =>
      request<VisitorPass[]>(
        `/visitor-passes/mine${status ? `?status=${status}` : ""}`,
        { token }
      ),
    create: (token: string, body: VisitorPassCreate) =>
      request<VisitorPass>("/visitor-passes", {
        method: "POST",
        body: JSON.stringify(body),
        token,
      }),
    cancel: (token: string, id: string) =>
      request<void>(`/visitor-passes/${id}`, { method: "DELETE", token }),
  },

  notifications: {
    register: (token: string, pushToken: string) =>
      request<void>("/notifications/register", {
        method: "POST",
        body: JSON.stringify({ token: pushToken }),
        token,
      }),
    unregister: (token: string, pushToken: string) =>
      request<void>("/notifications/unregister", {
        method: "POST",
        body: JSON.stringify({ token: pushToken }),
        token,
      }),
  },

  events: {
    list: (
      token: string,
      params: { limit?: number; cursor?: string; from?: string } = {}
    ) => {
      const q = new URLSearchParams();
      if (params.limit) q.set("limit", String(params.limit));
      if (params.cursor) q.set("cursor", params.cursor);
      if (params.from) q.set("from", params.from);
      return request<EventsPage>(`/events?${q}`, { token });
    },
  },

  parking: {
    listActive: (token: string) =>
      request<ParkingSession[]>("/parking-sessions/active", { token }),
    close: (token: string, id: string) =>
      request<ParkingSession>(`/parking-sessions/${id}/close`, {
        method: "POST",
        body: JSON.stringify({}),
        token,
      }),
    markPaid: (token: string, id: string) =>
      request<ParkingSession>(`/parking-sessions/${id}/mark-paid`, {
        method: "POST",
        body: JSON.stringify({}),
        token,
      }),
  },
};

// ── Types ─────────────────────────────────────────────────────────────────────

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
  kind: "entry" | "exit" | "parked" | "anpr";
  confidence: number | null;
  plate: PlateOut | null;
  vehicle: { type: string | null; color: string | null } | null;
}

export interface EventsPage {
  items: Event[];
  next_cursor: string | null;
}

export interface ParkingSession {
  id: string;
  site_id: string;
  plate_text: string | null;
  entry_ts: string | null;
  exit_ts: string | null;
  duration_s: number | null;
  amount_due: number | null;
  payment_status: "pending" | "paid" | "waived";
}

export interface AnalyticsOverview {
  events_today: number;
  active_sessions: number;
  revenue_today: number;
  open_alerts: number;
  gate_triggers_today: number;
  active_passes: number;
}

export type AlertStatus = "new" | "ack" | "snoozed" | "resolved";

export interface Alert {
  id: string;
  event_id: string;
  watchlist_id: string | null;
  status: AlertStatus;
  created_at: string;
  plate_text: string | null;
  watchlist_name: string | null;
  site_id: string | null;
}

export interface AlertsPage {
  items: Alert[];
  total: number;
  next_cursor: string | null;
}

export interface VisitorPass {
  id: string;
  plate: string;
  valid_from: string;
  valid_to: string;
  single_use: boolean;
  used: boolean;
  notes: string | null;
  pass_status: "active" | "upcoming" | "expired" | "used" | "unknown";
}

export interface VisitorPassCreate {
  plate: string;
  valid_from: string;
  valid_to: string;
  single_use?: boolean;
  notes?: string;
}
