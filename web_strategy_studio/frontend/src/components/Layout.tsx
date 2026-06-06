/**
 * Layout — general-purpose page layout with Header, Sidebar, main content, and StatusBar.
 *
 * Use this for pages that need the full application chrome (settings, reports, etc.).
 * For the strategy editor IDE layout, continue using AppShell which has the
 * draggable split pane and Monaco integration.
 *
 * Structure:
 *   ┌────────────────────────────────────┐
 *   │            Header                  │
 *   ├──────┬─────────────────────────────┤
 *   │      │                             │
 *   │ Side │         <Outlet />          │
 *   │ bar  │                             │
 *   │      │                             │
 *   ├──────┴─────────────────────────────┤
 *   │           StatusBar                │
 *   └────────────────────────────────────┘
 */
import { Outlet } from "react-router-dom";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";
import { StatusBar } from "./StatusBar";
import { cn } from "@/lib/utils";

interface LayoutProps {
  /** Override the default Outlet with custom children. */
  children?: React.ReactNode;
  /** Optional header center content. */
  headerCenter?: React.ReactNode;
  /** Optional header actions. */
  headerActions?: React.ReactNode;
  className?: string;
}

export function Layout({
  children,
  headerCenter,
  headerActions,
  className,
}: LayoutProps) {
  return (
    <div className="flex flex-col h-screen bg-background text-text-primary overflow-hidden">
      <Header center={headerCenter} actions={headerActions} />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar />

        <main className={cn("flex-1 overflow-auto p-6", className)}>
          {children ?? <Outlet />}
        </main>
      </div>

      <StatusBar />
    </div>
  );
}
