/**
 * StatusBar — bottom bar showing connection state, dirty flag, keyboard hints.
 */
import { useEffect, useState } from "react";

import { useEditorStore } from "../store/editorStore";

export function StatusBar() {
  const dirty = useEditorStore((s) => s.dirty);
  const sseConnected = useEditorStore((s) => s.sseConnected);
  const sseReconnecting = useEditorStore((s) => s.sseReconnecting);
  const runId = useEditorStore((s) => s.runId);
  const [viewportWidth, setViewportWidth] = useState(window.innerWidth);

  useEffect(() => {
    const ro = new ResizeObserver(() => setViewportWidth(window.innerWidth));
    ro.observe(document.documentElement);
    return () => ro.disconnect();
  }, []);

  const isPhone = viewportWidth < 480;

  const isMac = typeof navigator !== "undefined" &&
    (/Mac/.test(navigator.userAgent) || /Mac|iPod|iPhone|iPad/.test(navigator.platform));
  const mod = isMac ? "⌘" : "Ctrl+";

  let connLabel: string;
  let connColor: string;
  let connDot: string;
  if (sseReconnecting) {
    connLabel = "重连中…";
    connColor = "var(--state-warning)";
    connDot = "◌";
  } else if (sseConnected) {
    connLabel = runId ? "运行中" : "已连接";
    connColor = "var(--state-success)";
    connDot = "●";
  } else {
    connLabel = "空闲";
    connColor = "var(--text-dim)";
    connDot = "○";
  }

  return (
    <footer
      aria-label="状态栏"
      role="status"
      style={{
        height: isPhone ? 20 : 24,
        flexShrink: 0,
        background: "var(--bg-secondary)",
        borderTop: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
        paddingLeft: isPhone ? 8 : 12,
        paddingRight: isPhone ? 8 : 12,
        gap: isPhone ? 8 : 16,
        fontSize: isPhone ? 10 : 11,
        color: "var(--text-dim)",
        userSelect: "none",
        overflow: "hidden",
      }}
    >
      {/* Connection indicator */}
      <span
        aria-label={sseReconnecting ? "SSE 重连中" : sseConnected ? "SSE 已连接" : "SSE 未连接"}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          color: connColor,
        }}
      >
        <span aria-hidden="true" style={{ fontSize: 8 }}>
          {connDot}
        </span>
        {connLabel}
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

      {/* Keyboard hints - only on tablet/desktop */}
      {!isPhone && (
        <>
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
        </>
      )}
    </footer>
  );
}
