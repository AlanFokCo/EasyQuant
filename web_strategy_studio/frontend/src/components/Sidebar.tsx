/**
 * Sidebar — left icon-strip navigation.
 * Shows nav items + bottom theme toggle and logout.
 *
 * Uses the design-system CSS variables and Tailwind utility classes
 * while remaining backward-compatible with the existing AppShell layout.
 */
import { Code2, Database, GitCompare, History, LogOut, SunMoon } from "lucide-react";
import { useEditorStore } from "../store/editorStore";
import { useTheme } from "../hooks/useTheme";
import { logout } from "../api/client";
import { cn } from "@/lib/utils";

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
  const { theme, cycleTheme } = useTheme();

  const active = showHistory ? "history" : showCompare ? "compare" : showData ? "data" : "editor";

  function handleNav(id: NavItem["id"]) {
    useEditorStore.setState({
      showHistory: id === "history",
      showCompare: id === "compare",
      showData: id === "data",
    });
  }

  const themeLabel =
    theme === "dark" ? "深色主题" : theme === "light" ? "浅色主题" : "跟随系统";

  return (
    <aside
      aria-label="导航栏"
      className={cn(
        "w-12 shrink-0 flex flex-col items-center",
        "bg-surface border-r border-border",
        "py-2 gap-1 relative z-100"
      )}
    >
      {/* Brand mark */}
      <div
        className="w-7 h-7 flex items-center justify-center mb-2"
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
          className={cn(
            "w-9 h-9 rounded-md flex items-center justify-center",
            "transition-colors",
            active === item.id
              ? "bg-primary-bg text-primary"
              : "text-text-secondary hover:bg-surface-raised hover:text-text-primary"
          )}
        >
          {item.icon}
        </button>
      ))}

      <div className="flex-1" />

      {/* Divider before utility buttons */}
      <div className="w-6 h-px bg-border-subtle mb-1" />

      {/* Theme toggle */}
      <button
        type="button"
        aria-label={`当前: ${themeLabel}，点击切换主题`}
        title={`当前: ${themeLabel} (点击循环切换)`}
        onClick={cycleTheme}
        className={cn(
          "w-9 h-9 rounded-md flex items-center justify-center",
          "text-text-secondary hover:bg-surface-raised hover:text-text-primary",
          "transition-colors"
        )}
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
        className={cn(
          "w-9 h-9 rounded-md flex items-center justify-center",
          "text-text-muted hover:bg-[var(--state-error-bg)] hover:text-danger",
          "transition-colors"
        )}
      >
        <LogOut size={16} />
      </button>
    </aside>
  );
}
