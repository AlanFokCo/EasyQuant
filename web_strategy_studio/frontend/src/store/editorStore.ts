import { create } from "zustand";

type EditorState = {
  dirty: boolean;
  runId: string | null;
  sseConnected: boolean;
  setDirty: (v: boolean) => void;
  setRunId: (id: string | null) => void;
  setSseConnected: (v: boolean) => void;
};

export const useEditorStore = create<EditorState>((set) => ({
  dirty: false,
  runId: null,
  sseConnected: false,
  setDirty: (dirty) => set({ dirty }),
  setRunId: (runId) => set({ runId }),
  setSseConnected: (sseConnected) => set({ sseConnected }),
}));
