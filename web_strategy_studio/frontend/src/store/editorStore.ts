import { create } from "zustand";

export type ToastType = "success" | "error" | "info";

export type Toast = {
  id: string;
  type: ToastType;
  message: string;
};

export type Theme = "dark" | "light" | "system";

type EditorState = {
  dirty: boolean;
  runId: string | null;
  sseConnected: boolean;
  sseReconnecting: boolean;
  showHistory: boolean;
  showCompare: boolean;
  showData: boolean;
  showVersions: boolean;
  showTemplates: boolean;
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
  setShowVersions: (v: boolean) => void;
  setShowTemplates: (v: boolean) => void;
  setCompareIds: (ids: string[]) => void;
  addToast: (type: ToastType, message: string) => void;
  dismissToast: (id: string) => void;
  setTheme: (theme: Theme) => void;
  setCommandPaletteOpen: (open: boolean) => void;
};

let _toastCounter = 0;

const _storedTheme = (localStorage.getItem("eq_theme") as Theme | null) ?? "system";
// HIGH-20: per-tab runId via sessionStorage (not global localStorage)
const _storedRunId = sessionStorage.getItem("eq_studio_run_id") ?? null;

export const useEditorStore = create<EditorState>((set) => ({
  dirty: false,
  runId: _storedRunId,
  sseConnected: false,
  sseReconnecting: false,
  showHistory: false,
  showCompare: false,
  showData: false,
  showVersions: false,
  showTemplates: false,
  compareIds: [],
  toasts: [],
  theme: _storedTheme,
  commandPaletteOpen: false,
  setDirty: (dirty) => set({ dirty }),
  setRunId: (runId) => {
    // HIGH-20: Persist to sessionStorage (per-tab) for reattach-after-refresh
    if (runId) {
      sessionStorage.setItem("eq_studio_run_id", runId);
    } else {
      sessionStorage.removeItem("eq_studio_run_id");
    }
    set({ runId });
  },
  setSseConnected: (sseConnected) => set({ sseConnected }),
  setSseReconnecting: (sseReconnecting) => set({ sseReconnecting }),
  setShowHistory: (showHistory) => set({ showHistory, showCompare: false, showData: false, showVersions: false }),
  setShowCompare: (showCompare) => set({ showCompare, showHistory: false, showData: false, showVersions: false }),
  setShowData: (showData) => set({ showData, showHistory: false, showCompare: false, showVersions: false }),
  setShowVersions: (showVersions) => set({ showVersions, showHistory: false, showCompare: false, showData: false }),
  setShowTemplates: (showTemplates) => set({ showTemplates }),
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
