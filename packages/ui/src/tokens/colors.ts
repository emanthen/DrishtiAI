/**
 * DrishtiAI color system — section 4.2 of the product spec.
 *
 * Usage: import { colors } from "@drishtiai/ui/tokens"
 * In Tailwind: configured via the tailwind-preset (bg-ink, text-signal, etc.)
 */

export const colors = {
  /** Primary text on light; primary background on dark. */
  ink: "#0B0F14",

  /** Page background in light mode. */
  bone: "#F5F5F1",

  /** Action accent — interactive controls, primary buttons, focused states. */
  signal: "#2C6EFB",

  /** Watchlist hits, wrong-way, incidents. Use sparingly and always meaningfully. */
  alert: "#E14C3A",

  /** Recognized / known-vehicle successes. */
  confirm: "#1F8A5C",

  /** Secondary text. */
  steel: "#5B6470",

  /** Borders and dividers — light mode. */
  hairline: {
    light: "#E1E1DA",
    dark: "#252A31",
  },
} as const;

export type ColorKey = keyof typeof colors;
