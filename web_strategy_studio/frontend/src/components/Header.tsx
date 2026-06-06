/**
 * Header — top navigation bar with brand, breadcrumb area, and actions.
 *
 * Renders a slim bar at the top of the application with:
 * - Brand logo and title (left)
 * - Optional breadcrumb / context area (center)
 * - Action buttons: theme toggle, user menu (right)
 */
import { SunMoon, Activity } from "lucide-react";
import { useTheme } from "@/hooks/useTheme";
import { cn } from "@/lib/utils";

interface HeaderProps {
  /** Optional breadcrumb or context element rendered in the center. */
  center?: React.ReactNode;
  /** Optional action elements rendered before the theme toggle. */
  actions?: React.ReactNode;
  className?: string;
}

export function Header({ center, actions, className }: HeaderProps) {
  const { cycleTheme, theme } = useTheme();

  const themeLabel =
    theme === "dark" ? "深色主题" : theme === "light" ? "浅色主题" : "跟随系统";

  return (
    <header
      className={cn(
        "flex items-center h-11 px-4 gap-3 shrink-0",
        "bg-surface border-b border-border",
        "select-none",
        className
      )}
    >
      {/* ── Brand ────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 min-w-0">
        <Activity className="h-4 w-4 text-primary shrink-0" />
        <span className="text-sm font-semibold whitespace-nowrap">
          EasyQuant Studio
        </span>
      </div>

      {/* ── Center (breadcrumb / context) ─────────────────── */}
      {center && (
        <div className="flex-1 flex items-center justify-center min-w-0 overflow-hidden">
          {center}
        </div>
      )}
      {!center && <div className="flex-1" />}

      {/* ── Actions ─────────────────────────────────────────── */}
      <div className="flex items-center gap-1">
        {actions}

        {/* Theme toggle */}
        <button
          type="button"
          aria-label={`当前: ${themeLabel}，点击切换主题`}
          title={`当前: ${themeLabel} (点击循环切换)`}
          onClick={cycleTheme}
          className={cn(
            "h-8 w-8 inline-flex items-center justify-center rounded-md",
            "text-text-secondary hover:text-text-primary hover:bg-surface-raised",
            "transition-colors"
          )}
        >
          <SunMoon className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}
