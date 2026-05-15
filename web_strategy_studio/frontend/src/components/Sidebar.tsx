/**
 * Sidebar — left icon-strip navigation.
 * Shows nav items + bottom theme toggle.
 */
import { Code2, GitCompare, History, SunMoon } from "lucide-react";
import { useEditorStore } from "../store/editorStore";
import { useTheme } from "../hooks/useTheme";

type NavItem = {
  id: "editor" | "history" | "compare";
  icon: React.ReactNode;
  label: string;
};

const NAV_ITEMS: NavItem[] = [
  { id: "editor",  icon: <Code2  size={18} />, label: "策略编辑器 (Editor)" },
  { id: "history", icon: <History size={18} />, label: "回测历史 (⌘K ⌘H)" },
  { id: "compare", icon: <GitCompare size={18} />, label: "指标对比 (⌘K ⌘C)" },
];

export function Sidebar() {
  const showHistory = useEditorStore((s) => s.showHistory);
  const showCompare = useEditorStore((s) => s.showCompare);
  const setShowHistory = useEditorStore((s) => s.setShowHistory);
  const setShowCompare = useEditorStore((s) => s.setShowCompare);
  const { theme, setTheme } = useTheme();

  const active = showHistory ? "history" : showCompare ? "compare" : "editor";

  function handleNav(id: NavItem["id"]) {
    setShowHistory(id === "history");
    setShowCompare(id === "compare");
  }

  function cycleTheme() {
    if (theme === "dark") setTheme("light");
    else if (theme === "light") setTheme("system");
    else setTheme("dark");
  }

  const themeLabel = theme === "dark" ? "深色主题" : theme === "light" ? "浅色主题" : "跟随系统";

  return (
    <aside
      aria-label="导航栏"
      style={{
        width: 48,
        flexShrink: 0,
        background: "var(--bg-secondary)",
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        paddingTop: 8,
        paddingBottom: 8,
        gap: 4,
        zIndex: 10,
      }}
    >
      {/* Brand mark */}
      <div
        style={{
          width: 28,
          height: 28,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: 8,
        }}
        aria-hidden="true"
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
          <polyline
            points="22 12 18 12 15 21 9 3 6 12 2 12"
            stroke="var(--primary)"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>

      {/* Nav items */}
      {NAV_ITEMS.map((item) => (
        <button
          key={item.id}
          type="button"
          aria-label={item.label}
          title={item.label}
          onClick={() => handleNav(item.id)}
          style={{
            width: 36,
            height: 36,
            borderRadius: "var(--radius-md)",
            border: "none",
            background: active === item.id ? "var(--primary-bg)" : "transparent",
            color: active === item.id ? "var(--primary)" : "var(--text-secondary)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            transition: "background var(--motion-fast), color var(--motion-fast)",
          }}
        >
          {item.icon}
        </button>
      ))}

      <div style={{ flex: 1 }} />

      {/* Theme toggle */}
      <button
        type="button"
        aria-label={`当前: ${themeLabel}，点击切换主题`}
        title={`当前: ${themeLabel} (点击循环切换)`}
        onClick={cycleTheme}
        style={{
          width: 36,
          height: 36,
          borderRadius: "var(--radius-md)",
          border: "none",
          background: "transparent",
          color: "var(--text-secondary)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          transition: "color var(--motion-fast)",
        }}
      >
        <SunMoon size={16} />
      </button>
    </aside>
  );
}
