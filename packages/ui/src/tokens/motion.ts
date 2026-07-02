/** Motion tokens — section 4.6. No page-load flourishes. */
export const motion = {
  /** Micro-interactions: state changes */
  fast: "120ms ease-out",
  /** Panel transitions */
  panel: "200ms ease-out",

  /** Plate strip confidence underline pulse — the one deliberate moment. */
  platePulse: {
    keyframes: {
      "0%, 100%": { opacity: "1" },
      "50%": { opacity: "0.4" },
    },
    duration: "600ms",
    easing: "ease-in-out",
    iterationCount: 1,
  },
} as const;
