/**
 * DrishtiAI type system — section 4.3 of the product spec.
 *
 * Display/heading: Söhne → GT America → Inter Display (CSS var --font-display)
 * Body/UI: Inter at 14-15px (CSS var --font-sans)
 * Numeric/data (plates, timestamps, IDs): IBM Plex Mono (CSS var --font-mono)
 */

export const typography = {
  fontFamily: {
    display: ["Söhne", "GT America", "Inter Display", "system-ui", "sans-serif"],
    sans: ["Inter", "system-ui", "sans-serif"],
    mono: ["IBM Plex Mono", "Courier New", "monospace"],
  },

  scale: {
    h1: { fontSize: "22px", fontWeight: "500", lineHeight: "1.3" },
    h2: { fontSize: "18px", fontWeight: "500", lineHeight: "1.4" },
    h3: { fontSize: "15px", fontWeight: "500", lineHeight: "1.4" },
    body: { fontSize: "14px", fontWeight: "400", lineHeight: "1.5" },
    caption: { fontSize: "12px", fontWeight: "500", letterSpacing: "0.5px", lineHeight: "1.4" },
    plate: {
      fontSize: "18px",
      fontWeight: "500",
      letterSpacing: "0.5px",
      textTransform: "uppercase" as const,
      fontFamily: "IBM Plex Mono, Courier New, monospace",
    },
  },
} as const;
