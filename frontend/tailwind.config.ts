import type { Config } from "tailwindcss";

// Neo-brutalism design tokens — the single source of truth for the aesthetic.
// See SYSTEM_ARCHITECTURE.md and PRODUCT_REQUIREMENTS.md before editing.
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0A0A0A", // borders + text
        paper: "#FFFDF5", // base background
        brut: {
          yellow: "#FFD600",
          pink: "#FF4FA3",
          blue: "#2D5BFF",
          green: "#00C566",
          red: "#FF3B30",
          lilac: "#B388FF",
        },
      },
      fontFamily: {
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
        sans: ["'Inter'", "system-ui", "sans-serif"],
      },
      borderWidth: { "3": "3px", "5": "5px" },
      boxShadow: {
        // hard offset shadows, zero blur — the brutalist signature
        brut: "4px 4px 0 0 #0A0A0A",
        "brut-lg": "8px 8px 0 0 #0A0A0A",
        "brut-press": "1px 1px 0 0 #0A0A0A",
      },
      borderRadius: { brut: "2px" },
    },
  },
  plugins: [],
};

export default config;
