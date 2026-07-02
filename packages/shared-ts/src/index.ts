// Shared TypeScript types — generated from Pydantic schemas in packages/shared-python.
// Phase 0: hand-written stubs. Phase 1+: codegen from OpenAPI spec.

export type UUID = string;

export type PlanTier = "smb" | "mid" | "enterprise";

export type CameraKind = "ip" | "analog";
export type CameraRole = "anpr_lane" | "parking" | "perimeter" | "general";
export type HealthStatus = "online" | "offline" | "degraded" | "unknown";

export type EventKind =
  | "plate_read"
  | "line_cross"
  | "wrong_way"
  | "illegal_park"
  | "helmet_violation"
  | "watchlist_hit"
  | "gate_open"
  | "tamper"
  | "congestion";

export type AlertStatus = "new" | "ack" | "snoozed" | "resolved";

export type VehicleType =
  | "car"
  | "motorbike"
  | "scooter"
  | "auto_rickshaw"
  | "van"
  | "suv"
  | "truck"
  | "bus"
  | "other";

export type VehicleColor =
  | "white" | "black" | "silver" | "grey" | "red"
  | "blue" | "green" | "yellow" | "orange" | "brown"
  | "maroon" | "other";

export type PlateFormat = "embossed" | "devanagari" | "handwritten" | "unknown";
export type UserRole = "superadmin" | "site_admin" | "manager" | "guard" | "resident" | "auditor";

export interface Camera {
  id: UUID;
  site_id: UUID;
  name: string;
  kind: CameraKind;
  stream_url: string | null;
  role: CameraRole;
  health_status: HealthStatus;
  enabled: boolean;
}

export interface Plate {
  id: UUID;
  text: string;
  region: string | null;
  format_class: PlateFormat;
  vehicle_id: UUID | null;
}

export interface Event {
  id: UUID;
  site_id: UUID;
  camera_id: UUID;
  ts: string;
  kind: EventKind;
  vehicle_id: UUID | null;
  plate_id: UUID | null;
  snapshot_key: string | null;
  clip_key: string | null;
  confidence: number | null;
}

export interface Alert {
  id: UUID;
  event_id: UUID;
  watchlist_id: UUID | null;
  status: AlertStatus;
  ack_by: UUID | null;
  ack_at: string | null;
  created_at: string;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    detail?: Record<string, unknown>;
  };
}
