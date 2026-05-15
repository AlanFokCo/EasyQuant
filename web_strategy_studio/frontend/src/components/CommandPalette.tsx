/**
 * CommandPalette — Cmd+K launcher backed by cmdk.
 * Actions: jump to history, compare, run backtest, format, clear logs, toggle theme, docs.
 */
import { Command } from "cmdk";
import {
  BookOpen,
  Code2,
  GitCompare,
  History,
  Moon,
  Play,
  Sun,
  Trash2,
  SunMoon,
} from "lucide-react";

import { useEditorStore } from "../store/editorStore";
import { useTheme } from "../hooks/useTheme";

type Action = {
  id: string;
  label: string;
  group: string;
  icon: React.ReactNode;
  kbd?: string;
  onSelect: () => void;
};

type Props = {
  onRun: () => void;
  onFormat: () => void;
  onClearLogs: () => void;
};

export function CommandPalette({ onRun, onFormat, onClearLogs }: Props) {
  const open = useEditorStore((s) => s.commandPaletteOpen);
  const setOpen = useEditorStore((s) => s.setCommandPaletteOpen);
  const setShowHistory = useEditorStore((s) => s.setShowHistory);
  const setShowCompare = useEditorStore((s) => s.setShowCompare);
  const { setTheme } = useTheme();

  const actions: Action[] = [
    {
      id: "run",
      label: "运行回测",
      group: "操作",
      icon: <Play size={14} />,
      kbd: "⌘↵",
      onSelect: () => { setOpen(false); onRun(); },
    },
    {
      id: "format",
      label: "格式化代码",
      group: "操作",
      icon: <Code2 size={14} />,
      kbd: "⌘⇧F",
      onSelect: () => { setOpen(false); onFormat(); },
    },
    {
      id: "history",
      label: "查看回测历史",
      group: "导航",
      icon: <History size={14} />,
      kbd: "⌘K ⌘H",
      onSelect: () => {
        setOpen(false);
        setShowHistory(true);
        setShowCompare(false);
      },
    },
    {
      id: "compare",
      label: "指标对比",
      group: "导航",
      icon: <GitCompare size={14} />,
      kbd: "⌘K ⌘C",
      onSelect: () => {
        setOpen(false);
        setShowCompare(true);
        setShowHistory(false);
      },
    },
    {
      id: "clear-logs",
      label: "清空日志",
      group: "操作",
      icon: <Trash2 size={14} />,
      onSelect: () => { setOpen(false); onClearLogs(); },
    },
    {
      id: "theme-dark",
      label: "切换深色主题",
      group: "外观",
      icon: <Moon size={14} />,
      onSelect: () => { setOpen(false); setTheme("dark"); },
    },
    {
      id: "theme-light",
      label: "切换浅色主题",
      group: "外观",
      icon: <Sun size={14} />,
      onSelect: () => { setOpen(false); setTheme("light"); },
    },
    {
      id: "theme-system",
      label: "跟随系统主题",
      group: "外观",
      icon: <SunMoon size={14} />,
      onSelect: () => { setOpen(false); setTheme("system"); },
    },
    {
      id: "docs",
      label: "打开 eqlib 文档",
      group: "帮助",
      icon: <BookOpen size={14} />,
      onSelect: () => {
        setOpen(false);
        window.open("https://github.com/AlanFokCo/EasyQuant", "_blank", "noopener,noreferrer");
      },
    },
  ];

  // Group actions
  const groups = [...new Set(actions.map((a) => a.group))];

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        aria-hidden="true"
        onClick={() => setOpen(false)}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.65)",
          backdropFilter: "blur(4px)",
          zIndex: 900,
          animation: "eq-fade-in 120ms ease-out forwards",
        }}
      />

      {/* Palette dialog */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="命令面板"
        style={{
          position: "fixed",
          top: "20%",
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: 901,
          width: "min(640px, calc(100vw - 32px))",
          background: "var(--bg-secondary)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-lg)",
          overflow: "hidden",
          animation: "eq-slide-down 120ms ease-out forwards",
        }}
      >
        <Command
          loop
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              e.stopPropagation();
              setOpen(false);
            }
          }}
        >
          <Command.Input
            placeholder="搜索命令… (Esc 关闭)"
            aria-label="命令搜索"
            style={{
              width: "100%",
              padding: "14px 16px",
              background: "transparent",
              border: "none",
              borderBottom: "1px solid var(--border)",
              color: "var(--text)",
              fontFamily: "var(--font-stack)",
              fontSize: 15,
              outline: "none",
            }}
          />
          <Command.List
            style={{
              maxHeight: 380,
              overflowY: "auto",
              padding: "8px",
            }}
          >
            <Command.Empty
              style={{
                padding: "32px 16px",
                textAlign: "center",
                fontSize: 13,
                color: "var(--text-dim)",
              }}
            >
              未找到匹配命令
            </Command.Empty>

            {groups.map((group) => (
              <Command.Group
                key={group}
                heading={group}
              >
                {actions
                  .filter((a) => a.group === group)
                  .map((action) => (
                    <Command.Item
                      key={action.id}
                      value={action.label}
                      onSelect={action.onSelect}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                        padding: "9px 10px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: 13,
                        color: "var(--text)",
                        cursor: "pointer",
                      }}
                    >
                      <span style={{ color: "var(--text-secondary)", flexShrink: 0 }}>
                        {action.icon}
                      </span>
                      <span style={{ flex: 1 }}>{action.label}</span>
                      {action.kbd && (
                        <kbd
                          style={{
                            marginLeft: "auto",
                            fontSize: 11,
                            color: "var(--text-dim)",
                            fontFamily: "var(--mono)",
                            background: "var(--bg-tertiary)",
                            border: "1px solid var(--border)",
                            borderRadius: "var(--radius-sm)",
                            padding: "1px 5px",
                          }}
                        >
                          {action.kbd}
                        </kbd>
                      )}
                    </Command.Item>
                  ))}
              </Command.Group>
            ))}
          </Command.List>

          {/* Footer hint */}
          <div
            style={{
              display: "flex",
              gap: 16,
              padding: "8px 14px",
              borderTop: "1px solid var(--border)",
              fontSize: 11,
              color: "var(--text-dim)",
            }}
          >
            <span><kbd style={{ fontFamily: "var(--mono)" }}>↑↓</kbd> 导航</span>
            <span><kbd style={{ fontFamily: "var(--mono)" }}>↵</kbd> 执行</span>
            <span><kbd style={{ fontFamily: "var(--mono)" }}>Esc</kbd> 关闭</span>
          </div>
        </Command>
      </div>
    </>
  );
}
