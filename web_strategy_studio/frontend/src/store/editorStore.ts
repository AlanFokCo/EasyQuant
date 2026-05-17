import { create } from "zustand";

export type ToastType = "success" | "error" | "info";

export type Toast = {
  id: string;
  type: ToastType;
  message: string;
};

export type Theme = "dark" | "light" | "system";

const LS_RUN_KEY = "eq_studio_run_id";

type EditorState = {
  dirty: boolean;
  runId: string | null;
  sseConnected: boolean;
  sseReconnecting: boolean;
  showHistory: boolean;
  showCompare: boolean;
  showData: boolean;
  compareIds: string[];
  toasts: Toast[];
  theme: Theme;
  commandPaletteOpen: boolean;
  setDirty: (v: boolean) => void;
  setRunId: (id: string | null) => void;
  setSseConnected: (v: boolean) => void;
  setSseReconnecting: (v: boolean) => void;
  setShowHistory: (v: boolean) => void;
  setShowCompare: (v: boolean) => void;
  setShowData: (v: boolean) => void;
  setCompareIds: (ids: string[]) => void;
  addToast: (type: ToastType, message: string) => void;
  dismissToast: (id: string) => void;
  setTheme: (theme: Theme) => void;
  setCommandPaletteOpen: (open: boolean) => void;
};

let _toastCounter = 0;

const _storedTheme = (localStorage.getItem("eq_theme") as Theme | null) ?? "system";
// B7: restore runId from localStorage on page load
const _storedRunId = localStorage.getItem(LS_RUN_KEY) ?? null;

export const useEditorStore = create<EditorState>((set) => ({
  dirty: false,
  runId: _storedRunId,
  sseConnected: false,
  sseReconnecting: false,
  showHistory: false,
  showCompare: false,
  showData: false,
  compareIds: [],
  toasts: [],
  theme: _storedTheme,
  commandPaletteOpen: false,
  setDirty: (dirty) => set({ dirty }),
  setRunId: (runId) => {
    // Persist to localStorage so reattach-after-refresh works (B7)
    if (runId) {
      localStorage.setItem(LS_RUN_KEY, runId);
    } else {
      localStorage.removeItem(LS_RUN_KEY);
    }
    set({ runId });
  },
  setSseConnected: (sseConnected) => set({ sseConnected }),
  setSseReconnecting: (sseReconnecting) => set({ sseReconnecting }),
  setShowHistory: (showHistory) => set({ showHistory, showCompare: false, showData: false }),
  setShowCompare: (showCompare) => set({ showCompare, showHistory: false, showData: false }),
  setShowData: (showData) => set({ showData, showHistory: false, showCompare: false }),
  setCompareIds: (compareIds) => set({ compareIds }),
  addToast: (type, message) =>
    set((s) => {
      const id = `t${++_toastCounter}`;
      return { toasts: [...s.toasts, { id, type, message }] };
    }),
  dismissToast: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
  setTheme: (theme) => {
    localStorage.setItem("eq_theme", theme);
    set({ theme });
  },
  setCommandPaletteOpen: (commandPaletteOpen) => set({ commandPaletteOpen }),
}));
