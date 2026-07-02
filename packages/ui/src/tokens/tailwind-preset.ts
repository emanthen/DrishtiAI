import type { Config } from "tailwindcss";
import { colors } from "./colors";
import { radius } from "./radius";
import { typography } from "./typography";

export const drishtaiPreset: Partial<Config> = {
  theme: {
    colors: {
      transparent: "transparent",
      current: "currentColor",
      ink: colors.ink,
      bone: colors.bone,
      signal: colors.signal,
      alert: colors.alert,
      confirm: colors.confirm,
      steel: colors.steel,
      hairline: colors.hairline.light,
      "hairline-dark": colors.hairline.dark,
      white: "#ffffff",
      black: "#000000",
    },
    borderRadius: {
      none: "0",
      sm: radius.input,
      DEFAULT: radius.control,
      md: radius.control,
      lg: radius.card,
      full: radius.chip,
    },
    fontFamily: {
      sans: typography.fontFamily.sans,
      mono: typography.fontFamily.mono,
      display: typography.fontFamily.display,
    },
    extend: {
      animation: {
        "plate-pulse": "plate-pulse 600ms ease-in-out 1",
      },
      keyframes: {
        "plate-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
      },
      transitionDuration: {
        fast: "120ms",
        panel: "200ms",
      },
      transitionTimingFunction: {
        smooth: "ease-out",
      },
    },
  },
};
