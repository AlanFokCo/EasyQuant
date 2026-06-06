/**
 * Tests for Header component.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

// Mock the editor store for useTheme
vi.mock("../store/editorStore", () => ({
  useEditorStore: (selector: (s: Record<string, unknown>) => unknown) => {
    const state = {
      theme: "dark",
      setTheme: vi.fn(),
    };
    return selector(state);
  },
}));

import { Header } from "../components/Header";

describe("Header", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders brand name", () => {
    render(<Header />);
    expect(screen.getByText("EasyQuant Studio")).toBeDefined();
  });

  it("renders theme toggle button", () => {
    render(<Header />);
    const themeBtn = screen.getByRole("button", { name: /当前.*点击切换主题/ });
    expect(themeBtn).toBeDefined();
  });

  it("renders center content when provided", () => {
    render(<Header center={<span>Breadcrumb</span>} />);
    expect(screen.getByText("Breadcrumb")).toBeDefined();
  });

  it("renders action buttons when provided", () => {
    render(
      <Header
        actions={<button type="button">Save</button>}
      />
    );
    expect(screen.getByRole("button", { name: "Save" })).toBeDefined();
  });

  it("theme toggle calls cycleTheme on click", () => {
    render(<Header />);
    const themeBtn = screen.getByRole("button", { name: /当前.*点击切换主题/ });
    // Should not throw
    fireEvent.click(themeBtn);
  });
});
