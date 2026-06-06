/**
 * Design Tokens — single source of truth for the EQ Studio design system.
 *
 * These tokens mirror the CSS custom properties defined in index.css and are
 * intended for use in JavaScript/TypeScript contexts where CSS variables are
 * not directly accessible (e.g., chart configurations, dynamic styles).
 *
 * For component styling, prefer Tailwind utility classes or CSS variables.
 */

// ─── Colors ──────────────────────────────────────────────────────────────────

export const colors = {
  // Surfaces
  background: "#0d1117",
  surface: "#161b22",
  "surface-raised": "#1c2333",

  // Borders
  border: "#30363d",
  "border-subtle": "#21262d",

  // Brand
  primary: {
    DEFAULT: "#58a6ff",
    hover: "#79b8ff",
    bg: "rgba(88,166,255,0.10)",
  },

  // Semantic colors
  success: "#3fb950",
  warning: "#d29922",
  danger: "#f85149",
  info: "#58a6ff",

  // Market direction (A-share: red up, green down)
  "market-up": "#f85149",
  "market-down": "#3fb950",

  // Text
  text: {
    primary: "#e6edf3",
    secondary: "#8b949e",
    muted: "#6e7681",
    inverse: "#0d1117",
  },
} as const;

export const lightColors = {
  background: "#f6f8fa",
  surface: "#ffffff",
  "surface-raised": "#eaeef2",
  border: "#d0d7de",
  "border-subtle": "#e8ecf0",
  primary: {
    DEFAULT: "#0969da",
    hover: "#0a58ca",
    bg: "rgba(9,105,218,0.08)",
  },
  success: "#1a7f37",
  warning: "#9a6700",
  danger: "#cf222e",
  info: "#0969da",
  "market-up": "#cf222e",
  "market-down": "#1a7f37",
  text: {
    primary: "#1f2328",
    secondary: "#636c76",
    muted: "#9198a1",
    inverse: "#ffffff",
  },
} as const;

// ─── Spacing ─────────────────────────────────────────────────────────────────

export const spacing = {
  xs: "4px",
  sm: "8px",
  md: "12px",
  lg: "16px",
  xl: "24px",
  "2xl": "32px",
  "3xl": "48px",
  "4xl": "64px",
} as const;

// ─── Border Radius ───────────────────────────────────────────────────────────

export const borderRadius = {
  sm: "4px",
  DEFAULT: "6px",
  md: "6px",
  lg: "10px",
  xl: "16px",
  full: "9999px",
} as const;

// ─── Shadows ─────────────────────────────────────────────────────────────────

export const shadows = {
  sm: "0 1px 2px rgba(0,0,0,0.40)",
  DEFAULT: "0 2px 8px rgba(0,0,0,0.40)",
  md: "0 2px 8px rgba(0,0,0,0.40)",
  lg: "0 8px 32px rgba(0,0,0,0.50)",
  xl: "0 16px 48px rgba(0,0,0,0.60)",
} as const;

// ─── Transitions ─────────────────────────────────────────────────────────────

export const transitions = {
  fast: "120ms ease-out",
  DEFAULT: "180ms ease-out",
  slow: "240ms ease-out",
  "ease-out-expo": "cubic-bezier(0.16, 1, 0.3, 1)",
} as const;

// ─── Typography ──────────────────────────────────────────────────────────────

export const fontFamily = {
  sans: '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
  mono: '"SF Mono", "Fira Code", "Fira Mono", "Roboto Mono", Menlo, Consolas, monospace',
} as const;

export const fontSize = {
  "2xs": { size: "11px", lineHeight: "1.4" },
  xs: { size: "12px", lineHeight: "1.4" },
  sm: { size: "13px", lineHeight: "1.5" },
  base: { size: "14px", lineHeight: "1.5" },
  md: { size: "16px", lineHeight: "1.5" },
  lg: { size: "20px", lineHeight: "1.4" },
  xl: { size: "24px", lineHeight: "1.3" },
  display: { size: "32px", lineHeight: "1.25" },
} as const;

// ─── Keyframes ───────────────────────────────────────────────────────────────

export const keyframes = {
  "fade-in": {
    "0%": { opacity: "0" },
    "100%": { opacity: "1" },
  },
  "fade-in-up": {
    "0%": { opacity: "0", transform: "translateY(10px)" },
    "100%": { opacity: "1", transform: "translateY(0)" },
  },
  "slide-in-right": {
    "0%": { transform: "translateX(100%)", opacity: "0" },
    "100%": { transform: "translateX(0)", opacity: "1" },
  },
  "scale-in": {
    "0%": { transform: "scale(0.95)", opacity: "0" },
    "100%": { transform: "scale(1)", opacity: "1" },
  },
} as const;

export const animation = {
  "fade-in": "fade-in 0.2s ease-out",
  "fade-in-up": "fade-in-up 0.3s ease-out",
  "slide-in-right": "slide-in-right 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
  "scale-in": "scale-in 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
} as const;
