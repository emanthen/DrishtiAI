"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/auth";
import { api, type VehicleDetail } from "@/lib/api";
import { formatTs, relativeTime } from "@/lib/utils";

const COLOR_HEX: Record<string, string> = {
  white: "#f5f5f5", black: "#1a1a1a", silver: "#c0c0c0", grey: "#808080",
  red: "#dc2626", blue: "#2563eb", green: "#16a34a", yellow: "#ca8a04",
  orange: "#ea580c", brown: "#92400e", maroon: "#881337", other: "#6b7280",
};

function ColorSwatch({ color }: { color: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="w-3 h-3 rounded-full border border-hairline dark:border-hairline-dark shrink-0"
        style={{ backgroundColor: COLOR_HEX[color] ?? "#6b7280" }}
      />
      <span className="capitalize text-xs text-steel">{color}</span>
    </span>
  );
}

const VEHICLE_COLORS = [
  "white","black","silver","grey","red","blue","green","yellow","orange","brown","maroon","other"
];

export default function VehiclesPage() {
  const { accessToken } = useAuthStore();
  const [plateSearch, setPlateSearch] = useState("");
  const [colorFilter, setColorFilter] = useState("");
  const [debouncedPlate, setDebouncedPlate] = useState("");

  function handlePlateInput(val: string) {
    setPlateSearch(val);
    const t = setTimeout(() => setDebouncedPlate(val), 300);
    return () => clearTimeout(t);
  }

  const { data, isLoading, isError } = useQuery({
    queryKey: ["vehicles", debouncedPlate, colorFilter],
    queryFn: () =>
      api.vehicles.list(accessToken!, {
        plate: debouncedPlate || undefined,
        color: colorFilter || undefined,
        limit: 100,
      }),
    enabled: !!accessToken,
    staleTime: 20_000,
  });

  const vehicles = data ?? [];

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-medium text-ink dark:text-bone">Vehicles</h1>
          <p className="text-xs text-steel mt-0.5">
            Each vehicle is automatically created when its plate is first read.
            Color is detected from the frame above the plate.
          </p>
        </div>
        <span className="text-sm text-steel">{vehicles.length} shown</span>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <input
          type="text"
          placeholder="Search by plate"
          value={plateSearch}
          onChange={(e) => handlePlateInput(e.target.value)}
          className="w-56 rounded-[4px] border border-hairline dark:border-hairline-dark bg-white dark:bg-ink px-3 py-2 text-sm text-ink dark:text-bone focus:outline-none focus:ring-1 focus:ring-signal"
        />
        <select
          value={colorFilter}
          onChange={(e) => setColorFilter(e.target.value)}
          className="rounded-[4px] border border-hairline dark:border-hairline-dark bg-white dark:bg-ink px-3 py-2 text-sm text-ink dark:text-bone focus:outline-none focus:ring-1 focus:ring-signal"
        >
          <option value="">All colors</option>
          {VEHICLE_COLORS.map((c) => (
            <option key={c} value={c} className="capitalize">{c}</option>
          ))}
        </select>
        {(plateSearch || colorFilter) && (
          <button
            onClick={() => { setPlateSearch(""); setDebouncedPlate(""); setColorFilter(""); }}
            className="text-sm text-steel hover:text-ink dark:hover:text-bone transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {isLoading && <p className="text-sm text-steel">Loading…</p>}
      {isError && <p className="text-sm text-alert">Failed to load vehicles.</p>}

      {!isLoading && !isError && vehicles.length === 0 && (
        <div className="rounded-[12px] border border-hairline dark:border-hairline-dark p-8 text-center">
          <p className="text-sm text-steel">No vehicles found.</p>
        </div>
      )}

      {vehicles.length > 0 && (
        <div className="rounded-[12px] border border-hairline dark:border-hairline-dark overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline dark:border-hairline-dark bg-hairline/40 dark:bg-hairline-dark/40">
                <th className="text-left px-4 py-2 text-xs font-semibold text-steel">Plates</th>
                <th className="text-left px-4 py-2 text-xs font-semibold text-steel">Color</th>
                <th className="text-left px-4 py-2 text-xs font-semibold text-steel">Type</th>
                <th className="text-left px-4 py-2 text-xs font-semibold text-steel">First seen</th>
                <th className="text-left px-4 py-2 text-xs font-semibold text-steel">Last seen</th>
              </tr>
            </thead>
            <tbody>
              {vehicles.map((v) => (
                <VehicleRow key={v.id} vehicle={v} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function VehicleRow({ vehicle }: { vehicle: VehicleDetail }) {
  const plateTexts = vehicle.plates.map((p) => p.text).join(", ") || "—";

  return (
    <tr className="border-b border-hairline dark:border-hairline-dark last:border-0 hover:bg-hairline/30 dark:hover:bg-hairline-dark/30 transition-colors">
      <td className="px-4 py-2">
        <span className="font-mono text-xs font-semibold text-ink dark:text-bone tracking-wider">
          {plateTexts}
        </span>
      </td>
      <td className="px-4 py-2">
        {vehicle.color ? <ColorSwatch color={vehicle.color} /> : <span className="text-xs text-steel">—</span>}
      </td>
      <td className="px-4 py-2 text-xs text-steel capitalize">
        {vehicle.type ?? <span className="italic text-steel/60">unknown</span>}
      </td>
      <td className="px-4 py-2 text-xs text-steel">
        {vehicle.first_seen ? (
          <span title={formatTs(vehicle.first_seen)}>{relativeTime(vehicle.first_seen)}</span>
        ) : "—"}
      </td>
      <td className="px-4 py-2 text-xs text-steel">
        {vehicle.last_seen ? (
          <span title={formatTs(vehicle.last_seen)}>{relativeTime(vehicle.last_seen)}</span>
        ) : "—"}
      </td>
    </tr>
  );
}
