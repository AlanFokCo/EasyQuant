/**
 * Tests for LoginPage component.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

// Mock framer-motion to avoid animation issues in tests
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: { children: React.ReactNode; [key: string]: unknown }) => {
      // Strip motion-specific props, pass through the rest
      const { initial, animate, transition, whileHover, whileTap, ...rest } = props as Record<string, unknown>;
      void initial; void animate; void transition; void whileHover; void whileTap;
      return <div {...rest}>{children}</div>;
    },
  },
}));

// Mock the API client
vi.mock("../api/client", () => ({
  apiJson: vi.fn(),
  setToken: vi.fn(),
  getToken: () => null,
  apiOrigin: "",
}));

import { LoginPage } from "../pages/LoginPage";

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders brand header", () => {
    render(<LoginPage onLogin={vi.fn()} />);
    expect(screen.getByText("EasyQuant Studio")).toBeDefined();
  });

  it("renders tagline", () => {
    render(<LoginPage onLogin={vi.fn()} />);
    expect(screen.getByText("专业的量化策略开发平台")).toBeDefined();
  });

  it("renders login form with username and password fields", () => {
    render(<LoginPage onLogin={vi.fn()} />);
    expect(screen.getByLabelText("用户名")).toBeDefined();
    expect(screen.getByLabelText("密码")).toBeDefined();
  });

  it("renders login button", () => {
    render(<LoginPage onLogin={vi.fn()} />);
    expect(screen.getByRole("button", { name: "登录" })).toBeDefined();
  });

  it("renders footer text", () => {
    render(<LoginPage onLogin={vi.fn()} />);
    expect(screen.getByText(/事件驱动的量化回测框架/)).toBeDefined();
  });
});
