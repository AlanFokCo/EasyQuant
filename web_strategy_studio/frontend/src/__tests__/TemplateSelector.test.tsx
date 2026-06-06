/**
 * Tests for TemplateSelector component.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

// Mock react-query
vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({
    data: [
      {
        id: "double_ma",
        name: "双均线策略",
        description: "基于短期和长期均线的金叉/死叉信号",
        category: "trend",
        tags: ["均线", "趋势"],
      },
      {
        id: "momentum",
        name: "动量策略",
        description: "基于过去N日涨幅的动量因子策略",
        category: "trend",
        tags: ["动量"],
      },
      {
        id: "mean_reversion",
        name: "均值回归策略",
        description: "基于布林带的均值回归策略",
        category: "oscillation",
        tags: ["均值回归"],
      },
    ],
    isLoading: false,
  }),
  useMutation: () => ({
    mutate: vi.fn(),
  }),
}));

// Mock editor store
const mockSetShowTemplates = vi.fn();
const mockAddToast = vi.fn();
vi.mock("../store/editorStore", () => ({
  useEditorStore: (selector: (s: Record<string, unknown>) => unknown) => {
    const state = {
      setShowTemplates: mockSetShowTemplates,
      addToast: mockAddToast,
    };
    return selector(state);
  },
}));

import { TemplateSelector } from "../components/TemplateSelector";

describe("TemplateSelector", () => {
  const onSelect = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the modal header", () => {
    render(<TemplateSelector onSelect={onSelect} />);
    expect(screen.getByText("策略模板")).toBeDefined();
  });

  it("displays template names in the list", () => {
    render(<TemplateSelector onSelect={onSelect} />);
    expect(screen.getByText("双均线策略")).toBeDefined();
    expect(screen.getByText("动量策略")).toBeDefined();
    expect(screen.getByText("均值回归策略")).toBeDefined();
  });

  it("displays category labels", () => {
    render(<TemplateSelector onSelect={onSelect} />);
    // "趋势" appears twice (double_ma and momentum both have category "trend")
    expect(screen.getAllByText("趋势").length).toBe(2);
  });

  it("shows placeholder when no template selected", () => {
    render(<TemplateSelector onSelect={onSelect} />);
    expect(screen.getByText("从左侧选择一个模板")).toBeDefined();
  });

  it("has cancel and apply buttons", () => {
    render(<TemplateSelector onSelect={onSelect} />);
    expect(screen.getByText("取消")).toBeDefined();
    expect(screen.getByText("应用模板")).toBeDefined();
  });

  it("clicking close button dismisses modal", () => {
    render(<TemplateSelector onSelect={onSelect} />);
    // The × button is the close button in the header
    const closeBtn = screen.getByText("×");
    closeBtn.click();
    expect(mockSetShowTemplates).toHaveBeenCalledWith(false);
  });

  it("clicking cancel button dismisses modal", () => {
    render(<TemplateSelector onSelect={onSelect} />);
    const cancelBtn = screen.getByText("取消");
    cancelBtn.click();
    expect(mockSetShowTemplates).toHaveBeenCalledWith(false);
  });
});
