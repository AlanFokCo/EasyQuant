import { useEffect } from "react";

import { useEditorStore, Toast } from "../store/editorStore";

const ICONS: Record<string, string> = {
  success: "✓",
  error: "✗",
  info: "ℹ",
};

const COLORS: Record<string, { bg: string; border: string; text: string }> = {
  success: { bg: "var(--success-bg)", border: "rgba(63,185,80,0.4)", text: "var(--success)" },
  error: { bg: "var(--error-bg)", border: "rgba(248,81,73,0.4)", text: "var(--error)" },
  info: { bg: "var(--primary-bg)", border: "rgba(88,166,255,0.4)", text: "var(--primary)" },
};

function ToastItem({ toast }: { toast: Toast }) {
  const dismiss = useEditorStore((s) => s.dismissToast);
  const c = COLORS[toast.type];

  useEffect(() => {
    const t = setTimeout(() => dismiss(toast.id), 5000);
    return () => clearTimeout(t);
  }, [toast.id, dismiss]);

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "10px 14px",
        borderRadius: "var(--radius)",
        background: c.bg,
        border: `1px solid ${c.border}`,
        color: c.text,
        fontSize: 13,
        fontWeight: 500,
        minWidth: 260,
        boxShadow: "0 2px 8px rgba(0,0,0,0.3)",
      }}
    >
      <span style={{ fontSize: 16, fontWeight: 700 }}>{ICONS[toast.type]}</span>
      <span style={{ flex: 1 }}>{toast.message}</span>
      <button
        type="button"
        onClick={() => dismiss(toast.id)}
        style={{
          background: "none",
          border: "none",
          color: c.text,
          cursor: "pointer",
          fontSize: 14,
          padding: "0 4px",
          opacity: 0.6,
        }}
      >
        ×
      </button>
    </div>
  );
}

export function ToastContainer() {
  const toasts = useEditorStore((s) => s.toasts);
  if (!toasts.length) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="通知消息"
      style={{
        position: "fixed",
        top: 16,
        right: 16,
        zIndex: 2000,
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} />
      ))}
    </div>
  );
}
