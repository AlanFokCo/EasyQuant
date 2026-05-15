/**
 * StatusBar — bottom bar showing connection state, dirty flag, keyboard hints.
 */
import { useEditorStore } from "../store/editorStore";

export function StatusBar() {
  const dirty = useEditorStore((s) => s.dirty);
  const sseConnected = useEditorStore((s) => s.sseConnected);
  const runId = useEditorStore((s) => s.runId);

  const isMac = typeof navigator !== "undefined" &&
    (/Mac/.test(navigator.userAgent) || /Mac|iPod|iPhone|iPad/.test(navigator.platform));
  const mod = isMac ? "⌘" : "Ctrl+";

  return (
    <footer
      aria-label="状态栏"
      role="status"
      style={{
        height: 24,
        flexShrink: 0,
        background: "var(--bg-secondary)",
        borderTop: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
        paddingLeft: 12,
        paddingRight: 12,
        gap: 16,
        fontSize: 11,
        color: "var(--text-dim)",
        userSelect: "none",
        overflow: "hidden",
      }}
    >
      {/* Connection indicator */}
      <span
        aria-label={sseConnected ? "SSE 已连接" : "SSE 未连接"}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          color: sseConnected ? "var(--state-success)" : "var(--text-dim)",
        }}
      >
        <span aria-hidden="true" style={{ fontSize: 8 }}>
          {sseConnected ? "●" : "○"}
        </span>
        {sseConnected ? (runId ? "运行中" : "已连接") : "空闲"}
      </span>

      {/* Dirty flag */}
      {dirty && (
        <span
          aria-label="有未保存的修改"
          style={{ color: "var(--state-warning)" }}
        >
          ● 未保存
        </span>
      )}

      <div style={{ flex: 1 }} />

      {/* Keyboard hints */}
      <span aria-hidden="true">
        <kbd style={{ fontFamily: "var(--mono)", fontSize: 10 }}>{mod}S</kbd>{" "}
        保存+检查
      </span>
      <span aria-hidden="true">
        <kbd style={{ fontFamily: "var(--mono)", fontSize: 10 }}>{mod}↵</kbd>{" "}
        运行
      </span>
      <span aria-hidden="true">
        <kbd style={{ fontFamily: "var(--mono)", fontSize: 10 }}>{mod}K</kbd>{" "}
        命令面板
      </span>
    </footer>
  );
}
