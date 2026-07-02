import type { Config } from "tailwindcss";
import { drishtaiPreset } from "@drishtiai/ui/tokens/tailwind-preset";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/**/*.{ts,tsx}",
    "../../packages/ui/src/**/*.{ts,tsx}",
  ],
  presets: [drishtaiPreset],
  theme: {
    extend: {},
  },
  plugins: [],
};

export default config;
