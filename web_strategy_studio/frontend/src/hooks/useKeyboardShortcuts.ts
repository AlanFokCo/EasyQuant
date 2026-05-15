/**
 * useKeyboardShortcuts — registers global keydown handlers for IDE shortcuts.
 *
 * Shortcuts:
 *  Cmd+S          → save + lint
 *  Cmd+Enter      → run backtest
 *  Cmd+Shift+F    → format code
 *  Cmd+K          → open command palette (then Cmd+H = history, Cmd+C = compare)
 *  Esc            → close modals / command palette
 */
import { useEffect, useRef } from "react";

type ShortcutMap = {
  onSave?: () => void;
  onRun?: () => void;
  onFormat?: () => void;
  onTogglePalette?: () => void;
  onShowHistory?: () => void;
  onShowCompare?: () => void;
  onEscape?: () => void;
};

const isMac = typeof navigator !== "undefined" &&
  // navigator.platform is deprecated in newer browsers; fall back to userAgent
  (/Mac/.test(navigator.userAgent) || /Mac|iPod|iPhone|iPad/.test(navigator.platform));

function isMod(e: KeyboardEvent): boolean {
  return isMac ? e.metaKey : e.ctrlKey;
}

export function useKeyboardShortcuts(handlers: ShortcutMap) {
  // Use a ref so the handler is always current without re-registering
  const ref = useRef(handlers);
  ref.current = handlers;

  // Tracks whether we're in a Cmd+K chord waiting for the next key
  const chordActive = useRef(false);
  const chordTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      // Skip when focus is inside an <input> / <textarea> (unless it's Monaco)
      const target = e.target as HTMLElement;
      const isTypingField =
        (target.tagName === "INPUT" || target.tagName === "TEXTAREA") &&
        !target.classList.contains("monaco-mouse-cursor-text");
      if (isTypingField) return;

      const h = ref.current;

      // ── Chord: Cmd+K ──────────────────────────────────────────────────────
      if (chordActive.current) {
        chordActive.current = false;
        if (chordTimer.current) clearTimeout(chordTimer.current);

        if (isMod(e)) {
          if (e.key === "h" || e.key === "H") {
            e.preventDefault();
            h.onShowHistory?.();
            return;
          }
          if (e.key === "c" || e.key === "C") {
            e.preventDefault();
            h.onShowCompare?.();
            return;
          }
        }
        // Unrecognised chord — fall through to normal handling
      }

      // ── Esc ───────────────────────────────────────────────────────────────
      if (e.key === "Escape") {
        h.onEscape?.();
        return;
      }

      if (!isMod(e)) return;

      // ── Cmd+S ─────────────────────────────────────────────────────────────
      if (e.key === "s" || e.key === "S") {
        if (!e.shiftKey && !e.altKey) {
          e.preventDefault();
          h.onSave?.();
          return;
        }
      }

      // ── Cmd+Enter ─────────────────────────────────────────────────────────
      if (e.key === "Enter") {
        e.preventDefault();
        h.onRun?.();
        return;
      }

      // ── Cmd+Shift+F ───────────────────────────────────────────────────────
      if ((e.key === "f" || e.key === "F") && e.shiftKey) {
        e.preventDefault();
        h.onFormat?.();
        return;
      }

      // ── Cmd+K ─────────────────────────────────────────────────────────────
      if (e.key === "k" || e.key === "K") {
        if (!e.shiftKey) {
          e.preventDefault();
          chordActive.current = true;
          chordTimer.current = setTimeout(() => {
            chordActive.current = false;
            // Single Cmd+K = toggle command palette
            h.onTogglePalette?.();
          }, 500);
          return;
        }
      }
    }

    window.addEventListener("keydown", onKeyDown, { capture: true });
    return () => window.removeEventListener("keydown", onKeyDown, { capture: true });
  }, []);
}
