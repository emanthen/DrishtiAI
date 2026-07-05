export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
    login: (email: string, password: string, totp_code?: string) =>
      request<{ access_token: string; refresh_token: string; token_type: string }>(
        "/auth/login",
        { method: "POST", body: JSON.stringify({ email, password, ...(totp_code ? { totp_code } : {}) }) },
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

  analytics: {
    overview: (token: string, siteId?: string) =>
      request<AnalyticsOverview>(`/analytics/overview${siteId ? `?site_id=${siteId}` : ""}`, { token }),
    hourlyTraffic: (token: string, siteId?: string, days = 7) =>
      request<HourlyBucket[]>(`/analytics/hourly-traffic?days=${days}${siteId ? `&site_id=${siteId}` : ""}`, { token }),
    dailyRevenue: (token: string, siteId?: string, days = 14) =>
      request<DailyRevenue[]>(`/analytics/daily-revenue?days=${days}${siteId ? `&site_id=${siteId}` : ""}`, { token }),
    occupancy: (token: string, siteId?: string) =>
      request<OccupancyBucket[]>(`/analytics/occupancy${siteId ? `?site_id=${siteId}` : ""}`, { token }),
    topPlates: (token: string, siteId?: string, days = 30, limit = 10) =>
      request<TopPlate[]>(`/analytics/top-plates?days=${days}&limit=${limit}${siteId ? `&site_id=${siteId}` : ""}`, { token }),
  },

  visitorPasses: {
    list: (token: string, params: VisitorPassParams = {}) => {
      const q = new URLSearchParams();
      if (params.siteId) q.set("site_id", params.siteId);
      if (params.status) q.set("status", params.status);
      if (params.limit) q.set("limit", String(params.limit));
      if (params.cursor) q.set("cursor", params.cursor);
      return request<VisitorPassPage>(`/visitor-passes?${q}`, { token });
    },
    mine: (token: string, status?: string) =>
      request<VisitorPass[]>(
        `/visitor-passes/mine${status ? `?status=${status}` : ""}`,
        { token },
      ),
    create: (token: string, body: VisitorPassCreate) =>
      request<VisitorPass>("/visitor-passes", { method: "POST", body: JSON.stringify(body), token }),
    get: (token: string, id: string) =>
      request<VisitorPass>(`/visitor-passes/${id}`, { token }),
    cancel: (token: string, id: string) =>
      request<void>(`/visitor-passes/${id}`, { method: "DELETE", token }),
  },

  gates: {
    listControllers: (token: string, siteId?: string) =>
      request<GateController[]>(
        `/gates/controllers${siteId ? `?site_id=${siteId}` : ""}`,
        { token },
      ),
    createController: (token: string, body: GateControllerCreate) =>
      request<GateController>("/gates/controllers", { method: "POST", body: JSON.stringify(body), token }),
    patchController: (token: string, id: string, body: Partial<GateControllerCreate> & { enabled?: boolean }) =>
      request<GateController>(`/gates/controllers/${id}`, { method: "PATCH", body: JSON.stringify(body), token }),
    deleteController: (token: string, id: string) =>
      request<void>(`/gates/controllers/${id}`, { method: "DELETE", token }),
    trigger: (token: string, id: string) =>
      request<GateTriggerLog>(`/gates/controllers/${id}/trigger`, { method: "POST", body: "{}", token }),
    controllerLog: (token: string, id: string, limit = 50) =>
      request<GateTriggerLog[]>(`/gates/controllers/${id}/log?limit=${limit}`, { token }),
    listRules: (token: string, params: { cameraId?: string; controllerId?: string } = {}) => {
      const q = new URLSearchParams();
      if (params.cameraId) q.set("camera_id", params.cameraId);
      if (params.controllerId) q.set("controller_id", params.controllerId);
      return request<GateRule[]>(`/gates/rules?${q}`, { token });
    },
    createRule: (token: string, body: GateRuleCreate) =>
      request<GateRule>("/gates/rules", { method: "POST", body: JSON.stringify(body), token }),
    patchRule: (token: string, id: string, body: Partial<GateRuleCreate> & { enabled?: boolean }) =>
      request<GateRule>(`/gates/rules/${id}`, { method: "PATCH", body: JSON.stringify(body), token }),
    deleteRule: (token: string, id: string) =>
      request<void>(`/gates/rules/${id}`, { method: "DELETE", token }),
  },

  parking: {
    listActive: (token: string, siteId?: string) =>
      request<ParkingSession[]>(
        `/parking-sessions/active${siteId ? `?site_id=${siteId}` : ""}`,
        { token },
      ),
    list: (token: string, params: ParkingParams = {}) => {
      const q = new URLSearchParams();
      if (params.siteId) q.set("site_id", params.siteId);
      if (params.activeOnly) q.set("active_only", "true");
      if (params.paymentStatus) q.set("payment_status", params.paymentStatus);
      if (params.limit) q.set("limit", String(params.limit));
      if (params.cursor) q.set("cursor", params.cursor);
      return request<ParkingPage>(`/parking-sessions?${q}`, { token });
    },
    close: (token: string, id: string) =>
      request<ParkingSession>(`/parking-sessions/${id}/close`, { method: "POST", body: "{}", token }),
    markPaid: (token: string, id: string) =>
      request<ParkingSession>(`/parking-sessions/${id}/mark-paid`, { method: "POST", body: "{}", token }),
    waive: (token: string, id: string) =>
      request<ParkingSession>(`/parking-sessions/${id}/waive`, { method: "POST", body: "{}", token }),
  },

  tariffs: {
    list: (token: string, siteId?: string) =>
      request<Tariff[]>(`/tariffs${siteId ? `?site_id=${siteId}` : ""}`, { token }),
    create: (token: string, body: TariffCreate) =>
      request<Tariff>("/tariffs", { method: "POST", body: JSON.stringify(body), token }),
    patch: (token: string, id: string, body: Partial<TariffCreate>) =>
      request<Tariff>(`/tariffs/${id}`, { method: "PATCH", body: JSON.stringify(body), token }),
    delete: (token: string, id: string) =>
      request<void>(`/tariffs/${id}`, { method: "DELETE", token }),
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

export interface AnalyticsOverview {
  events_today: number;
  active_sessions: number;
  revenue_today: number;
  open_alerts: number;
  gate_triggers_today: number;
  active_passes: number;
}

export interface HourlyBucket {
  hour: number;
  count: number;
}

export interface DailyRevenue {
  date: string;
  revenue: number;
  sessions: number;
}

export interface OccupancyBucket {
  hour: string;
  entries: number;
  exits: number;
}

export interface TopPlate {
  plate_text: string;
  count: number;
}

export interface VisitorPass {
  id: string;
  site_id: string;
  host_user_id: string | null;
  plate: string;
  valid_from: string;
  valid_to: string;
  single_use: boolean;
  used: boolean;
  notes: string | null;
  created_at: string;
  pass_status: "active" | "upcoming" | "expired" | "used" | "unknown";
}

export interface VisitorPassCreate {
  site_id?: string;
  plate: string;
  valid_from: string;
  valid_to: string;
  single_use?: boolean;
  notes?: string;
}

export interface VisitorPassPage {
  items: VisitorPass[];
  total: number;
  next_cursor: string | null;
}

export interface VisitorPassParams {
  siteId?: string;
  status?: string;
  limit?: number;
  cursor?: string;
}

export type GateKind = "webhook" | "onvif";
export type GateTriggerCondition = "any_plate" | "watchlist_match" | "permit_valid";

export interface GateController {
  id: string;
  site_id: string;
  name: string;
  kind: GateKind;
  config: Record<string, unknown>;
  open_pulse_ms: number;
  enabled: boolean;
  created_at: string;
}

export interface GateControllerCreate {
  site_id: string;
  name: string;
  kind?: GateKind;
  config?: Record<string, unknown>;
  open_pulse_ms?: number;
}

export interface GateRule {
  id: string;
  camera_id: string;
  gate_controller_id: string;
  trigger_on: GateTriggerCondition;
  watchlist_id: string | null;
  priority: number;
  enabled: boolean;
  created_at: string;
}

export interface GateRuleCreate {
  camera_id: string;
  gate_controller_id: string;
  trigger_on?: GateTriggerCondition;
  watchlist_id?: string;
  priority?: number;
}

export interface GateTriggerLog {
  id: string;
  gate_rule_id: string | null;
  gate_controller_id: string;
  event_id: string | null;
  plate_text: string | null;
  triggered_at: string;
  success: boolean;
  error_msg: string | null;
}

export type PaymentStatus = "pending" | "paid" | "waived" | "failed";

export interface ParkingSession {
  id: string;
  site_id: string;
  plate_id: string | null;
  entry_event_id: string | null;
  exit_event_id: string | null;
  duration_s: number | null;
  amount_due: number | null;
  payment_status: PaymentStatus;
  created_at: string;
  plate_text: string | null;
  entry_ts: string | null;
  exit_ts: string | null;
}

export interface ParkingPage {
  items: ParkingSession[];
  total: number;
  next_cursor: string | null;
}

export interface ParkingParams {
  siteId?: string;
  activeOnly?: boolean;
  paymentStatus?: PaymentStatus;
  limit?: number;
  cursor?: string;
}

export interface Tariff {
  id: string;
  site_id: string;
  name: string;
  rules_json: Record<string, unknown>;
  active: boolean;
}

export interface TariffCreate {
  site_id: string;
  name: string;
  rules_json: Record<string, unknown>;
  active?: boolean;
}

export interface AlertCounts {
  new: number;
  ack: number;
  snoozed: number;
  resolved: number;
  total_new: number;
}
