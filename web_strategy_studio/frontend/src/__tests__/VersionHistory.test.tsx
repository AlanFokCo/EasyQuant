/**
 * Tests for VersionHistory component.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

// Mock react-query
vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({
    data: [
      { version: 3, label: "latest", content_hash: "abc", created_at: "2025-06-06T10:00:00Z" },
      { version: 2, label: null, content_hash: "def", created_at: "2025-06-06T09:00:00Z" },
      { version: 1, label: "initial", content_hash: "ghi", created_at: "2025-06-06T08:00:00Z" },
    ],
    isLoading: false,
  }),
  useMutation: () => ({
    mutate: vi.fn(),
  }),
  useQueryClient: () => ({
    invalidateQueries: vi.fn(),
  }),
}));

// Mock editor store
vi.mock("../store/editorStore", () => ({
  useEditorStore: (selector: (s: Record<string, unknown>) => unknown) => {
    const state = {
      setShowVersions: vi.fn(),
      addToast: vi.fn(),
    };
    return selector(state);
  },
}));

// Mock useTheme
vi.mock("../hooks/useTheme", () => ({
  useTheme: () => ({ resolvedTheme: "dark" }),
  monacoThemeName: () => "eq-dark",
}));

import { VersionHistory } from "../components/VersionHistory";

describe("VersionHistory", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the version history header", () => {
    render(<VersionHistory strategyId="strat_123" currentVersion={3} />);
    expect(screen.getByText("版本历史")).toBeDefined();
  });

  it("displays version numbers", () => {
    render(<VersionHistory strategyId="strat_123" currentVersion={3} />);
    expect(screen.getByText("v3")).toBeDefined();
    expect(screen.getByText("v2")).toBeDefined();
    expect(screen.getByText("v1")).toBeDefined();
  });

  it("shows current badge for current version", () => {
    render(<VersionHistory strategyId="strat_123" currentVersion={3} />);
    expect(screen.getByText("当前")).toBeDefined();
  });

  it("shows version labels", () => {
    render(<VersionHistory strategyId="strat_123" currentVersion={3} />);
    expect(screen.getByText("latest")).toBeDefined();
    expect(screen.getByText("initial")).toBeDefined();
  });

  it("shows restore buttons for non-current versions", () => {
    render(<VersionHistory strategyId="strat_123" currentVersion={3} />);
    const restoreButtons = screen.getAllByText("恢复到此版本");
    expect(restoreButtons.length).toBe(2); // v2 and v1
  });

  it("shows diff buttons for versions with predecessors", () => {
    render(<VersionHistory strategyId="strat_123" currentVersion={3} />);
    const diffButtons = screen.getAllByText(/对比 v/);
    expect(diffButtons.length).toBe(2); // v3 compare v2, v2 compare v1
  });
});
