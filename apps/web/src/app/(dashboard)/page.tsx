"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useAuthStore } from "@/store/auth";
import { api, type Event } from "@/lib/api";
import { CameraTile } from "@/components/ui/camera-tile";
import { EventsTable } from "@/components/ui/events-table";

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

export default function LiveViewPage() {
  const { accessToken } = useAuthStore();
  const [liveEvents, setLiveEvents] = useState<Event[]>([]);
  const [newEventIds, setNewEventIds] = useState<Set<string>>(new Set());
  const wsRef = useRef<WebSocket | null>(null);

  const { data: cameras } = useQuery({
    queryKey: ["cameras"],
    queryFn: () => api.cameras.list(accessToken!),
    enabled: !!accessToken,
    refetchInterval: 30_000,
  });

  // WebSocket live event feed
  useEffect(() => {
    if (!accessToken) return;
    const ws = new WebSocket(`${WS_BASE}/ws/events`);
    wsRef.current = ws;

    ws.onmessage = (msg) => {
      try {
        const payload = JSON.parse(msg.data);
        const event: Event = {
          id: payload.event_id,
          site_id: payload.site_id,
          camera_id: payload.camera_id,
          ts: payload.ts,
          kind: payload.kind,
          vehicle_id: null,
          plate_id: null,
          snapshot_key: payload.snapshot_key ?? null,
          clip_key: null,
          confidence: payload.confidence ?? null,
          plate: payload.plate ? { id: "", text: payload.plate, region: null, format_class: "embossed" } : null,
        };
        setLiveEvents((prev) => [event, ...prev].slice(0, 100));
        setNewEventIds((prev) => new Set([...prev, event.id]));
        setTimeout(() => {
          setNewEventIds((prev) => {
            const next = new Set(prev);
            next.delete(event.id);
            return next;
          });
        }, 2000);
      } catch {}
    };

    return () => ws.close();
  }, [accessToken]);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-lg font-medium text-ink dark:text-bone">Live view</h1>

      {/* Camera grid */}
      {cameras && cameras.length > 0 && (
        <section>
          <h2 className="text-xs font-medium text-steel uppercase tracking-wide mb-3">
            Cameras ({cameras.length})
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {cameras.slice(0, 6).map((cam) => (
              <CameraTile key={cam.id} camera={cam} token={accessToken!} />
            ))}
          </div>
        </section>
      )}

      {/* Live events */}
      <section>
        <h2 className="text-xs font-medium text-steel uppercase tracking-wide mb-3">
          Recent events
        </h2>
        <div className="rounded-[12px] border border-hairline dark:border-hairline-dark">
          <EventsTable events={liveEvents} newEventIds={newEventIds} />
        </div>
      </section>
    </div>
  );
}
