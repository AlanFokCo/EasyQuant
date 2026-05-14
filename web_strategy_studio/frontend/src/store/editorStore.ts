import { create } from "zustand";

export type ToastType = "success" | "error" | "info";

export type Toast = {
  id: string;
  type: ToastType;
  message: string;
};

type EditorState = {
  dirty: boolean;
  runId: string | null;
  sseConnected: boolean;
  showHistory: boolean;
  showCompare: boolean;
  compareIds: string[];
  toasts: Toast[];
  setDirty: (v: boolean) => void;
  setRunId: (id: string | null) => void;
  setSseConnected: (v: boolean) => void;
  setShowHistory: (v: boolean) => void;
  setShowCompare: (v: boolean) => void;
  setCompareIds: (ids: string[]) => void;
  addToast: (type: ToastType, message: string) => void;
  dismissToast: (id: string) => void;
};

let _toastCounter = 0;

export const useEditorStore = create<EditorState>((set) => ({
  dirty: false,
  runId: null,
  sseConnected: false,
  showHistory: false,
  showCompare: false,
  compareIds: [],
  toasts: [],
  setDirty: (dirty) => set({ dirty }),
  setRunId: (runId) => set({ runId }),
  setSseConnected: (sseConnected) => set({ sseConnected }),
  setShowHistory: (showHistory) => set({ showHistory }),
  setShowCompare: (showCompare) => set({ showCompare }),
  setCompareIds: (compareIds) => set({ compareIds }),
  addToast: (type, message) =>
    set((s) => {
      const id = `t${++_toastCounter}`;
      return { toasts: [...s.toasts, { id, type, message }] };
    }),
  dismissToast: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));
