export const COLOR_HEX: Record<string, string> = {
  white:   "#f5f5f5",
  black:   "#1a1a1a",
  silver:  "#c0c0c0",
  grey:    "#808080",
  red:     "#dc2626",
  blue:    "#2563eb",
  green:   "#16a34a",
  yellow:  "#ca8a04",
  orange:  "#ea580c",
  brown:   "#92400e",
  maroon:  "#881337",
  other:   "#6b7280",
  unknown: "#6b7280",
};

interface ColorSwatchProps {
  color: string;
  size?: "sm" | "md";
  showLabel?: boolean;
}

export function ColorSwatch({ color, size = "sm", showLabel = true }: ColorSwatchProps) {
  const hex = COLOR_HEX[color] ?? COLOR_HEX.other;
  const dotCls = size === "sm" ? "w-3 h-3" : "w-3.5 h-3.5";
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={`${dotCls} rounded-full border border-hairline dark:border-hairline-dark shrink-0`}
        style={{ backgroundColor: hex }}
      />
      {showLabel && <span className="text-xs text-steel capitalize">{color}</span>}
    </span>
  );
}
