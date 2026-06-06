/**
 * Tailwind CSS v4 — minimal config file.
 *
 * Most theme customization is now in src/index.css using @theme directives.
 * This file is kept for content scanning and dark-mode class strategy.
 */
import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  plugins: [],
} satisfies Config;
