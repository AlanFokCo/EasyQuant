import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        "bg-secondary": "var(--bg-secondary)",
        "bg-tertiary": "var(--bg-tertiary)",
        border: "var(--border)",
        primary: "var(--primary)",
        "market-up": "var(--market-up)",
        "market-down": "var(--market-down)",
        "state-success": "var(--state-success)",
        "state-error": "var(--state-error)",
        "state-warning": "var(--state-warning)",
        text: "var(--text)",
        "text-secondary": "var(--text-secondary)",
        "text-dim": "var(--text-dim)",
      },
      fontFamily: {
        sans: ["var(--font-stack)"],
        mono: ["var(--mono)"],
      },
      spacing: {
        1: "4px",
        2: "8px",
        3: "12px",
        4: "16px",
        6: "24px",
        8: "32px",
      },
      fontSize: {
        "2xs": ["11px", "1.4"],
        xs: ["12px", "1.4"],
        sm: ["13px", "1.5"],
        base: ["14px", "1.5"],
        md: ["16px", "1.5"],
        lg: ["20px", "1.4"],
        xl: ["24px", "1.3"],
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
      },
      transitionDuration: {
        120: "120ms",
        180: "180ms",
        240: "240ms",
      },
    },
  },
  plugins: [],
} satisfies Config;
