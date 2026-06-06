/**
 * StatusBar — bottom bar showing connection state, dirty flag, keyboard hints.
 *
 * Uses the design-system CSS variables and Tailwind utility classes.
 */
import { useEffect, useState } from "react";
import { useEditorStore } from "../store/editorStore";
import { cn } from "@/lib/utils";

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
  let connColorClass: string;
  let connDot: string;
  if (sseReconnecting) {
    connLabel = "重连中…";
    connColorClass = "text-warning";
    connDot = "◌";
  } else if (sseConnected) {
    connLabel = runId ? "运行中" : "已连接";
    connColorClass = "text-success";
    connDot = "●";
  } else {
    connLabel = "空闲";
    connColorClass = "text-text-muted";
    connDot = "○";
  }

  return (
    <footer
      aria-label="状态栏"
      role="status"
      className={cn(
        "shrink-0 flex items-center",
        "bg-surface border-t border-border",
        "select-none overflow-hidden",
        isPhone ? "h-5 px-2 gap-2 text-[10px]" : "h-6 px-3 gap-4 text-[11px]"
      )}
      style={{ color: "var(--text-dim)" }}
    >
      {/* Connection indicator */}
      <span
        aria-label={sseReconnecting ? "SSE 重连中" : sseConnected ? "SSE 已连接" : "SSE 未连接"}
        className={cn("flex items-center gap-1", connColorClass)}
      >
        <span aria-hidden="true" className="text-[8px]">
          {connDot}
        </span>
        {connLabel}
      </span>

      {/* Dirty flag */}
      {dirty && (
        <span aria-label="有未保存的修改" className="text-warning">
          ● 未保存
        </span>
      )}

      <div className="flex-1" />

      {/* Keyboard hints - only on tablet/desktop */}
      {!isPhone && (
        <>
          <span aria-hidden="true">
            <kbd className="font-mono text-[10px]">{mod}S</kbd>{" "}
            保存+检查
          </span>
          <span aria-hidden="true">
            <kbd className="font-mono text-[10px]">{mod}↵</kbd>{" "}
            运行
          </span>
          <span aria-hidden="true">
            <kbd className="font-mono text-[10px]">{mod}K</kbd>{" "}
            命令面板
          </span>
        </>
      )}
    </footer>
  );
}
