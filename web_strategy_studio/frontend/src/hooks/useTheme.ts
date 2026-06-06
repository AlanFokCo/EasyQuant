/**
 * useTheme — applies [data-theme] to <html> and syncs Monaco editor theme.
 * Three modes: "dark" | "light" | "system" (follows prefers-color-scheme).
 *
 * Also exposes helper to cycle through themes for toggle buttons.
 */
import { useEffect, useCallback } from "react";
import { useEditorStore, type Theme } from "../store/editorStore";

function _resolveTheme(theme: Theme): "dark" | "light" {
  if (theme === "system") {
    return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }
  return theme;
}

export function useTheme() {
  const theme = useEditorStore((s) => s.theme);
  const setTheme = useEditorStore((s) => s.setTheme);

  useEffect(() => {
    const apply = () => {
      const resolved = _resolveTheme(theme);
      document.documentElement.setAttribute("data-theme", resolved);
    };

    apply();

    // Re-apply when system preference changes (only relevant for "system" mode)
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, [theme]);

  const resolvedTheme = _resolveTheme(theme);

  const cycleTheme = useCallback(() => {
    if (theme === "dark") setTheme("light");
    else if (theme === "light") setTheme("system");
    else setTheme("dark");
  }, [theme, setTheme]);

  return { theme, resolvedTheme, setTheme, cycleTheme };
}

export function monacoThemeName(resolvedTheme: "dark" | "light"): string {
  return resolvedTheme === "light" ? "vs" : "eq-dark";
}
