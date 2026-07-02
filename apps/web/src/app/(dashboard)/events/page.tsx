"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/auth";
import { api } from "@/lib/api";
import { EventsTable } from "@/components/ui/events-table";

export default function EventsPage() {
  const { accessToken } = useAuthStore();
  const [plateSearch, setPlateSearch] = useState("");
  const [debouncedPlate, setDebouncedPlate] = useState("");

  // Simple debounce
  function handlePlateInput(val: string) {
    setPlateSearch(val);
    const timer = setTimeout(() => setDebouncedPlate(val), 300);
    return () => clearTimeout(timer);
  }

  const { data, isLoading } = useQuery({
    queryKey: ["events", debouncedPlate],
    queryFn: () =>
      api.events.list(accessToken!, {
        plate: debouncedPlate || undefined,
        limit: 100,
      }),
    enabled: !!accessToken,
    staleTime: 10_000,
  });

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-medium text-ink dark:text-bone">Events</h1>
      </div>

      {/* Search */}
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Search by plate (partial ok)"
          value={plateSearch}
          onChange={(e) => handlePlateInput(e.target.value)}
          className="w-72 rounded-[4px] border border-hairline dark:border-hairline-dark bg-white dark:bg-ink px-3 py-2 text-sm text-ink dark:text-bone focus:outline-none focus:ring-1 focus:ring-signal"
        />
        {plateSearch && (
          <button
            onClick={() => { setPlateSearch(""); setDebouncedPlate(""); }}
            className="text-sm text-steel hover:text-ink transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      <div className="rounded-[12px] border border-hairline dark:border-hairline-dark">
        <EventsTable
          events={data?.items ?? []}
          isLoading={isLoading}
        />
      </div>

      {data?.next_cursor && (
        <p className="text-xs text-steel text-center">
          Showing first 100 results. Narrow the search to see more.
        </p>
      )}
    </div>
  );
}
