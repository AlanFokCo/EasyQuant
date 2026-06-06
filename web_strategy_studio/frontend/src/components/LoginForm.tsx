/**
 * LoginForm — presentational login form using the new design system.
 *
 * Uses the shadcn/ui Button and Input components with validation support.
 * The parent component handles the actual login logic via the onSubmit callback.
 */
import { useState } from "react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { cn } from "@/lib/utils";

interface LoginFormProps {
  onSubmit: (data: { username: string; password: string }) => void | Promise<void>;
  isLoading?: boolean;
  error?: string;
}

export function LoginForm({ onSubmit, isLoading = false, error }: LoginFormProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const canSubmit = !isLoading && username.trim().length > 0 && password.length > 0;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    onSubmit({ username: username.trim(), password });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Error banner */}
      {error && (
        <div
          role="alert"
          className={cn(
            "text-sm px-3 py-2 rounded-md",
            "text-danger bg-[var(--state-error-bg)]"
          )}
        >
          {error}
        </div>
      )}

      {/* Username */}
      <div className="space-y-1.5">
        <label htmlFor="login-username" className="label">
          用户名
        </label>
        <Input
          id="login-username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="请输入用户名"
          autoComplete="username"
          autoFocus
          disabled={isLoading}
        />
      </div>

      {/* Password */}
      <div className="space-y-1.5">
        <label htmlFor="login-password" className="label">
          密码
        </label>
        <Input
          id="login-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="请输入密码"
          autoComplete="current-password"
          disabled={isLoading}
        />
      </div>

      {/* Submit */}
      <Button
        type="submit"
        className="w-full"
        disabled={!canSubmit}
      >
        {isLoading ? (
          <span className="flex items-center gap-2">
            <span className="spinner spinner-sm" />
            登录中…
          </span>
        ) : (
          "登录"
        )}
      </Button>
    </form>
  );
}
