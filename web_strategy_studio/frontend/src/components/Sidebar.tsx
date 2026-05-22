/**
 * Sidebar — left icon-strip navigation.
 * Shows nav items + bottom theme toggle.
 */
import { Code2, Database, GitCompare, History, LogOut, SunMoon } from "lucide-react";
import { useEditorStore } from "../store/editorStore";
import { useTheme } from "../hooks/useTheme";
import { logout } from "../api/client";

type NavItem = {
  id: "editor" | "history" | "data" | "compare";
  icon: React.ReactNode;
  label: string;
};

const NAV_ITEMS: NavItem[] = [
  { id: "editor",  icon: <Code2  size={18} />, label: "策略编辑器" },
  { id: "history", icon: <History size={18} />, label: "回测历史" },
  { id: "data",    icon: <Database size={18} />, label: "数据管理" },
  { id: "compare", icon: <GitCompare size={18} />, label: "指标对比" },
];

export function Sidebar() {
  const showHistory = useEditorStore((s) => s.showHistory);
  const showCompare = useEditorStore((s) => s.showCompare);
  const showData = useEditorStore((s) => s.showData);
  const { theme, setTheme } = useTheme();

  const active = showHistory ? "history" : showCompare ? "compare" : showData ? "data" : "editor";

  function handleNav(id: NavItem["id"]) {
    useEditorStore.setState({
      showHistory: id === "history",
      showCompare: id === "compare",
      showData: id === "data",
    });
  }

  function cycleTheme() {
    if (theme === "dark") setTheme("light");
    else if (theme === "light") setTheme("system");
    else setTheme("dark");
  }

  const themeLabel = theme === "dark" ? "深色主题" : theme === "light" ? "浅色主题" : "跟随系统";

  const navBtnStyle = (isActive: boolean): React.CSSProperties => ({
    width: 36,
    height: 36,
    borderRadius: "var(--radius-md)",
    border: "none",
    background: isActive ? "var(--primary-bg)" : "transparent",
    color: isActive ? "var(--primary)" : "var(--text-secondary)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
    transition: "background var(--motion-fast), color var(--motion-fast)",
  });

  const utilBtnStyle: React.CSSProperties = {
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
    transition: "background var(--motion-fast), color var(--motion-fast)",
  };

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
        padding: "var(--spacing-sm) 0",
        gap: 4,
        position: "relative",
        zIndex: 100,
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
          marginBottom: "var(--spacing-sm)",
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
          style={navBtnStyle(active === item.id)}
          onMouseEnter={(e) => {
            if (active !== item.id) {
              e.currentTarget.style.background = "var(--bg-tertiary)";
            }
          }}
          onMouseLeave={(e) => {
            if (active !== item.id) {
              e.currentTarget.style.background = "transparent";
            }
          }}
        >
          {item.icon}
        </button>
      ))}

      <div style={{ flex: 1 }} />

      {/* Divider before utility buttons */}
      <div
        style={{
          width: 24,
          height: 1,
          background: "var(--border-subtle)",
          marginBottom: 4,
        }}
      />

      {/* Theme toggle */}
      <button
        type="button"
        aria-label={`当前: ${themeLabel}，点击切换主题`}
        title={`当前: ${themeLabel} (点击循环切换)`}
        onClick={cycleTheme}
        style={utilBtnStyle}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = "var(--bg-tertiary)";
          e.currentTarget.style.color = "var(--text)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "transparent";
          e.currentTarget.style.color = "var(--text-secondary)";
        }}
      >
        <SunMoon size={16} />
      </button>

      {/* Logout */}
      <button
        type="button"
        aria-label="退出登录"
        title="退出登录"
        onClick={() => {
          logout();
          window.location.reload();
        }}
        style={{ ...utilBtnStyle, color: "var(--text-dim)" }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = "var(--state-error-bg)";
          e.currentTarget.style.color = "var(--state-error)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "transparent";
          e.currentTarget.style.color = "var(--text-dim)";
        }}
      >
        <LogOut size={16} />
      </button>
    </aside>
  );
}