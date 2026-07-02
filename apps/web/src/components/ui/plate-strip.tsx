"use client";

import Image from "next/image";
import { cn } from "@/lib/utils";

interface PlateStripProps {
  plateText: string;
  confidence: number | null;
  snapshotUrl?: string | null;
  /** Show the pulse animation on the confidence underline (new reads). */
  isNew?: boolean;
  className?: string;
}

/**
 * The plate-strip: the product's visual signature.
 *
 * Renders the plate image (or a placeholder) in the actual plate aspect ratio,
 * with the OCR text in monospace beneath it and a confidence underline.
 * Confidence underline pulses once on new reads.
 *
 * Section 4.5 of the product spec.
 */
export function PlateStrip({
  plateText,
  confidence,
  snapshotUrl,
  isNew = false,
  className,
}: PlateStripProps) {
  const confidenceColor = getConfidenceColor(confidence);

  return (
    <div className={cn("flex flex-col gap-1 w-fit", className)}>
      {/* Plate image — 4:1 aspect ratio */}
      <div className="relative w-32 h-8 bg-hairline dark:bg-hairline-dark rounded-[4px] overflow-hidden">
        {snapshotUrl ? (
          <Image
            src={snapshotUrl}
            alt={`Plate ${plateText}`}
            fill
            className="object-cover"
            sizes="128px"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <span className="text-[10px] text-steel">No image</span>
          </div>
        )}
      </div>

      {/* OCR text */}
      <span className="plate-text text-ink dark:text-bone leading-none">
        {plateText}
      </span>

      {/* Confidence underline — color-coded, pulses once on new reads */}
      <div
        className={cn(
          "h-[2px] rounded-full transition-colors",
          isNew && "animate-plate-pulse",
        )}
        style={{ backgroundColor: confidenceColor, width: "100%" }}
        title={confidence !== null ? `Confidence: ${(confidence * 100).toFixed(0)}%` : undefined}
      />
    </div>
  );
}

function getConfidenceColor(confidence: number | null): string {
  if (confidence === null) return "#5B6470"; // steel
  if (confidence >= 0.85) return "#1F8A5C"; // confirm
  if (confidence >= 0.65) return "#E1A23A"; // amber
  return "#E14C3A"; // alert
}
