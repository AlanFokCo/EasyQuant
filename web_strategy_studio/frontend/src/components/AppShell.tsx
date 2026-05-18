/**
 * AppShell — three-panel IDE layout.
 *
 * Layout (horizontal):
 *   [Sidebar 48px] [Workbench flex] → [Editor | Divider | RightPane]
 *   [StatusBar 24px spanning full width]
 *
 * Split ratio between Editor and RightPane is draggable and persisted in
 * localStorage under "eq_split_editor_pct" (percentage of workbench width).
 *
 * Responsive:
 *   ≥768px : dual-pane (editor + right panel side by side, draggable split)
 *   <768   : single column + top-tab switcher
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Sidebar } from "./Sidebar";
import { StatusBar } from "./StatusBar";

const LS_KEY_SPLIT = "eq_split_editor_pct";
const MIN_PCT = 20;
const MAX_PCT = 85;

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

function readSplitPct(): number {
  const v = parseFloat(localStorage.getItem(LS_KEY_SPLIT) ?? "");
  if (Number.isFinite(v)) return clamp(v, MIN_PCT, MAX_PCT);
  return 68; // default: editor takes 68% width
}

type Props = {
  /** Left / centre panel — the Monaco editor + toolbar */
  editor: React.ReactNode;
  /** Right panel — params / logs / history */
  rightPane: React.ReactNode;
};

export function AppShell({ editor, rightPane }: Props) {
  const [editorPct, setEditorPct] = useState(readSplitPct);
  const [dragging, setDragging] = useState(false);
  const workbenchRef = useRef<HTMLDivElement>(null);
  const [viewportWidth, setViewportWidth] = useState(window.innerWidth);

  // Persist split ratio
  useEffect(() => {
    localStorage.setItem(LS_KEY_SPLIT, String(editorPct));
  }, [editorPct]);

  // Track viewport width for responsive behaviour
  useEffect(() => {
    const ro = new ResizeObserver(() => setViewportWidth(window.innerWidth));
    ro.observe(document.documentElement);
    return () => ro.disconnect();
  }, []);

  // ── Drag logic ────────────────────────────────────────────────────────────
  const onDividerMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      setDragging(true);

      const wb = workbenchRef.current;
      if (!wb) return;
      const rect = wb.getBoundingClientRect();

      const onMove = (ev: MouseEvent) => {
        const newPct = ((ev.clientX - rect.left) / rect.width) * 100;
        setEditorPct(clamp(newPct, MIN_PCT, MAX_PCT));
      };
      const onUp = () => {
        setDragging(false);
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      };

      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },
    []
  );

  // ── Responsive helpers ───────────────────────────────────────────────────
  const isNarrow = viewportWidth < 768;

  // For narrow, track active "tab"
  const [narrowTab, setNarrowTab] = useState<"editor" | "panel">("editor");

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        overflow: "hidden",
        background: "var(--bg)",
        color: "var(--text)",
      }}
    >
      {/* Narrow top-tab bar */}
      {isNarrow && (
        <div
          role="tablist"
          aria-label="视图切换"
          style={{
            display: "flex",
            background: "var(--bg-secondary)",
            borderBottom: "1px solid var(--border)",
            flexShrink: 0,
          }}
        >
          {(["editor", "panel"] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              role="tab"
              aria-selected={narrowTab === tab}
              aria-controls={`tab-panel-${tab}`}
              onClick={() => setNarrowTab(tab)}
              style={{
                flex: 1,
                padding: "8px 12px",
                border: "none",
                borderBottom: narrowTab === tab ? "2px solid var(--primary)" : "2px solid transparent",
                background: "transparent",
                color: narrowTab === tab ? "var(--primary)" : "var(--text-secondary)",
                fontSize: 13,
                fontWeight: 500,
                cursor: "pointer",
              }}
            >
              {tab === "editor" ? "编辑器" : "参数 / 日志"}
            </button>
          ))}
        </div>
      )}

      {/* Main row */}
      <div
        style={{
          flex: 1,
          minHeight: 0,
          display: "flex",
          flexDirection: "row",
          overflow: "hidden",
          position: "relative",
          zIndex: 0,
        }}
      >
        {/* Sidebar (hidden on narrow) */}
        {!isNarrow && <Sidebar />}

        {/* Workbench */}
        {isNarrow ? (
          /* Narrow: single-column with top tabs */
          <div style={{ flex: 1, minWidth: 0, overflow: "hidden" }}>
            <div
              id="tab-panel-editor"
              role="tabpanel"
              aria-label="编辑器面板"
              style={{
                display: narrowTab === "editor" ? "flex" : "none",
                flexDirection: "column",
                height: "100%",
              }}
            >
              {editor}
            </div>
            <div
              id="tab-panel-panel"
              role="tabpanel"
              aria-label="参数与日志面板"
              style={{
                display: narrowTab === "panel" ? "flex" : "none",
                flexDirection: "column",
                height: "100%",
                overflowY: "auto",
              }}
            >
              {rightPane}
            </div>
          </div>
        ) : (
          /* ≥768px: dual pane with draggable split */
          <div
            ref={workbenchRef}
            style={{
              flex: 1,
              minWidth: 0,
              display: "flex",
              overflow: "hidden",
            }}
          >
            {/* Editor pane */}
            <div
              style={{
                flex: `0 0 ${editorPct}%`,
                minWidth: 0,
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
              }}
            >
              {editor}
            </div>

            {/* Draggable divider */}
            <div
              className={`eq-divider-h${dragging ? " dragging" : ""}`}
              role="separator"
              aria-orientation="vertical"
              aria-label="调整编辑器与参数面板的宽度比例"
              aria-valuenow={Math.round(editorPct)}
              aria-valuemin={MIN_PCT}
              aria-valuemax={MAX_PCT}
              tabIndex={0}
              onMouseDown={onDividerMouseDown}
              onKeyDown={(e) => {
                if (e.key === "ArrowLeft") setEditorPct((p) => clamp(p - 2, MIN_PCT, MAX_PCT));
                if (e.key === "ArrowRight") setEditorPct((p) => clamp(p + 2, MIN_PCT, MAX_PCT));
              }}
            />

            {/* Right panel */}
            <div
              style={{
                flex: 1,
                minWidth: 240,
                overflow: "hidden",
                display: "flex",
                flexDirection: "column",
              }}
            >
              {rightPane}
            </div>
          </div>
        )}
      </div>

      {/* Status Bar */}
      <StatusBar />

      {/* Prevent text selection while dragging */}
      {dragging && (
        <style>{`* { user-select: none !important; }`}</style>
      )}
    </div>
  );
}
