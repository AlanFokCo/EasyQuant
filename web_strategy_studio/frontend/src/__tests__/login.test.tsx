/**
 * Tests for LoginForm component.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { LoginForm } from "@/components/LoginForm";

describe("LoginForm", () => {
  it("renders username and password fields", () => {
    render(<LoginForm onSubmit={vi.fn()} />);
    expect(screen.getByLabelText("用户名")).toBeDefined();
    expect(screen.getByLabelText("密码")).toBeDefined();
  });

  it("renders login button", () => {
    render(<LoginForm onSubmit={vi.fn()} />);
    expect(screen.getByRole("button", { name: "登录" })).toBeDefined();
  });

  it("disables submit when fields are empty", () => {
    render(<LoginForm onSubmit={vi.fn()} />);
    const btn = screen.getByRole("button", { name: "登录" });
    expect(btn.getAttribute("disabled")).not.toBeNull();
  });

  it("enables submit when both fields have values", () => {
    render(<LoginForm onSubmit={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("用户名"), {
      target: { value: "admin" },
    });
    fireEvent.change(screen.getByLabelText("密码"), {
      target: { value: "secret" },
    });

    const btn = screen.getByRole("button", { name: "登录" });
    expect(btn.getAttribute("disabled")).toBeNull();
  });

  it("calls onSubmit with credentials on form submit", async () => {
    const onSubmit = vi.fn();
    render(<LoginForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("用户名"), {
      target: { value: "admin" },
    });
    fireEvent.change(screen.getByLabelText("密码"), {
      target: { value: "password123" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "登录" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledOnce();
      expect(onSubmit).toHaveBeenCalledWith({
        username: "admin",
        password: "password123",
      });
    });
  });

  it("shows error message when provided", () => {
    render(<LoginForm onSubmit={vi.fn()} error="用户名或密码错误" />);
    expect(screen.getByRole("alert").textContent).toBe("用户名或密码错误");
  });

  it("shows loading state", () => {
    render(<LoginForm onSubmit={vi.fn()} isLoading />);
    expect(screen.getByText("登录中…")).toBeDefined();
    // Button should be disabled during loading
    const btns = screen.getAllByRole("button");
    const submitBtn = btns.find((b) => b.textContent?.includes("登录中…"));
    expect(submitBtn?.getAttribute("disabled")).not.toBeNull();
  });

  it("disables inputs during loading", () => {
    render(<LoginForm onSubmit={vi.fn()} isLoading />);
    expect(screen.getByLabelText("用户名").getAttribute("disabled")).not.toBeNull();
    expect(screen.getByLabelText("密码").getAttribute("disabled")).not.toBeNull();
  });
});
