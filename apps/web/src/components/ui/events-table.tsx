"use client";

import { PlateStrip } from "./plate-strip";
import { formatTs, relativeTime } from "@/lib/utils";
import type { Event } from "@/lib/api";

interface EventsTableProps {
  events: Event[];
  isLoading?: boolean;
  newEventIds?: Set<string>;
}

export function EventsTable({ events, isLoading, newEventIds }: EventsTableProps) {
  if (isLoading && events.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-steel">Loading events…</div>
    );
  }

  if (!isLoading && events.length === 0) {
    return (
      <div className="py-12 text-center">
        <p className="text-sm text-ink dark:text-bone">No plates matched.</p>
        <p className="mt-1 text-xs text-steel">
          Try a partial plate or widen the date range.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-hairline dark:border-hairline-dark">
            <th className="py-2 px-3 text-left text-xs font-medium text-steel uppercase tracking-wide">
              Plate
            </th>
            <th className="py-2 px-3 text-left text-xs font-medium text-steel uppercase tracking-wide">
              Time
            </th>
            <th className="py-2 px-3 text-left text-xs font-medium text-steel uppercase tracking-wide">
              Kind
            </th>
            <th className="py-2 px-3 text-left text-xs font-medium text-steel uppercase tracking-wide">
              Vehicle
            </th>
            <th className="py-2 px-3 text-left text-xs font-medium text-steel uppercase tracking-wide">
              Camera
            </th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr
              key={event.id}
              className="border-b border-hairline dark:border-hairline-dark hover:bg-hairline dark:hover:bg-hairline-dark transition-colors"
            >
              <td className="py-2 px-3">
                {event.plate ? (
                  <PlateStrip
                    plateText={event.plate.text}
                    confidence={event.confidence}
                    isNew={newEventIds?.has(event.id)}
                  />
                ) : (
                  <span className="text-steel text-xs">—</span>
                )}
              </td>
              <td className="py-2 px-3">
                <span className="font-mono text-xs text-ink dark:text-bone">
                  {formatTs(event.ts)}
                </span>
                <span className="block text-[10px] text-steel">
                  {relativeTime(event.ts)}
                </span>
              </td>
              <td className="py-2 px-3">
                <KindChip kind={event.kind} />
              </td>
              <td className="py-2 px-3">
                {event.vehicle?.color ? (
                  <span className="inline-flex items-center gap-1.5">
                    <ColorDot color={event.vehicle.color} />
                    <span className="text-xs text-steel capitalize">{event.vehicle.color}</span>
                  </span>
                ) : (
                  <span className="text-steel text-xs">—</span>
                )}
              </td>
              <td className="py-2 px-3 font-mono text-xs text-steel">
                {event.camera_id.slice(0, 8)}…
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const KIND_STYLES: Record<string, { label: string; cls: string }> = {
  plate_read:   { label: "Plate read",    cls: "bg-confirm/15 text-confirm" },
  watchlist_hit:{ label: "Watchlist hit", cls: "bg-alert/15 text-alert" },
  wrong_way:    { label: "Wrong way",     cls: "bg-alert/15 text-alert" },
  illegal_park: { label: "Illegal park",  cls: "bg-alert/10 text-alert" },
  gate_open:    { label: "Gate open",     cls: "bg-signal/15 text-signal" },
};

function KindChip({ kind }: { kind: string }) {
  const cfg = KIND_STYLES[kind] ?? { label: kind, cls: "bg-steel/10 text-steel" };
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${cfg.cls}`}>
      {cfg.label}
    </span>
  );
}

const COLOR_HEX: Record<string, string> = {
  white:  "#f5f5f5",
  black:  "#1a1a1a",
  silver: "#c0c0c0",
  grey:   "#808080",
  red:    "#dc2626",
  blue:   "#2563eb",
  green:  "#16a34a",
  yellow: "#ca8a04",
  orange: "#ea580c",
  brown:  "#92400e",
  maroon: "#881337",
  other:  "#6b7280",
};

function ColorDot({ color }: { color: string }) {
  const hex = COLOR_HEX[color] ?? "#6b7280";
  return (
    <span
      className="inline-block w-3 h-3 rounded-full border border-hairline dark:border-hairline-dark shrink-0"
      style={{ backgroundColor: hex }}
      title={color}
    />
  );
}
