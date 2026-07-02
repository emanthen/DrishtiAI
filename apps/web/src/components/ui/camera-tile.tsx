"use client";

import { useEffect, useRef, useState } from "react";
import type { Camera } from "@/lib/api";

interface CameraTileProps {
  camera: Camera;
  token: string;
}

/**
 * Live camera tile: streams MJPEG from /api/stream/{id}/mjpeg
 * Phase 1: MJPEG. Phase 2: HLS via hls.js.
 */
export function CameraTile({ camera, token }: CameraTileProps) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [healthy, setHealthy] = useState(camera.health_status === "online");
  const [error, setError] = useState(false);

  const streamUrl = `/api/stream/${camera.id}/mjpeg`;

  useEffect(() => {
    setHealthy(camera.health_status === "online");
  }, [camera.health_status]);

  return (
    <div className="rounded-[12px] border border-hairline dark:border-hairline-dark overflow-hidden bg-ink aspect-video relative">
      {/* Stream */}
      {!error ? (
        <img
          ref={imgRef}
          src={streamUrl}
          alt={`Live feed: ${camera.name}`}
          className="w-full h-full object-cover"
          onError={() => setError(true)}
        />
      ) : (
        <div className="w-full h-full flex items-center justify-center">
          <p className="text-xs text-steel">Stream unavailable</p>
        </div>
      )}

      {/* Camera name + health badge overlay */}
      <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between px-3 py-2 bg-gradient-to-t from-ink/80 to-transparent">
        <span className="text-xs font-medium text-white truncate">{camera.name}</span>
        <HealthDot status={camera.health_status} />
      </div>
    </div>
  );
}

function HealthDot({ status }: { status: Camera["health_status"] }) {
  const colorMap = {
    online: "bg-confirm",
    offline: "bg-alert",
    degraded: "bg-yellow-500",
    unknown: "bg-steel",
  };
  return (
    <span
      className={`w-2 h-2 rounded-full shrink-0 ${colorMap[status]}`}
      title={status}
    />
  );
}
