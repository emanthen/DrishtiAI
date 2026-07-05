"use client";

import { PlateStrip } from "./plate-strip";
import { KindChip } from "./kind-chip";
import { ColorSwatch } from "./color-swatch";
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
                  <ColorSwatch color={event.vehicle.color} />
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

