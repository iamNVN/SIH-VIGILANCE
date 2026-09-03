/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["IBM Plex Sans", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
      colors: {
        // Dark-surface neutrals (validated dataviz palette -- references/palette.md)
        surface: {
          page: "#0b1120",
          raised: "#0b1120",
          card: "#111827",
          hover: "#1f2937",
          border: "rgba(255,255,255,0.08)",
        },
        ink: {
          primary: "#ffffff",
          secondary: "#9ca3af",
          muted: "#6b7280",
        },
        // Categorical series (fixed order -- never reassign/cycle)
        series: {
          1: "#3b82f6", // blue
          2: "#d95926", // orange
          3: "#199e70", // aqua
          4: "#c98500", // yellow
          5: "#d55181", // magenta
          6: "#008300", // green
          7: "#9085e9", // violet
          8: "#e66767", // red
        },
        // Status palette, reserved meaning -- never reused as series colors
        status: {
          good: "#0ca30c",
          warning: "#fab219",
          serious: "#ec835a",
          critical: "#d03b3b",
        },
        brand: {
          50: "#eef4ff",
          400: "#5598e7",
          500: "#3987e5",
          600: "#2a78d6",
          700: "#1c5cab",
        },
      },
    },
  },
  plugins: [],
};
