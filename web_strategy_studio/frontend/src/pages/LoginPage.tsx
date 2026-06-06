/**
 * LoginPage — login page with the new design system and Framer Motion.
 *
 * Features:
 * - Centered card layout with dark background
 * - Smooth entrance animation via Framer Motion
 * - Brand header with heartbeat icon
 * - Error handling and loading state
 */
import { useState } from "react";
import { motion } from "framer-motion";
import { Activity } from "lucide-react";
import { LoginForm } from "../components/LoginForm";
import { apiJson, setToken } from "../api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";

interface Props {
  onLogin: () => void;
}

export function LoginPage({ onLogin }: Props) {
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin(data: { username: string; password: string }) {
    setError("");
    setLoading(true);
    try {
      const resp = await apiJson<{
        access_token: string;
        role?: string;
        session_id?: string;
      }>("/api/v1/auth/login", { method: "POST", body: JSON.stringify(data) });
      setToken(resp.access_token);
      onLogin();
    } catch (e: unknown) {
      const raw = e instanceof Error ? e.message : "登录失败";
      // Parse structured error envelope from the backend (Module E)
      let code = "";
      let detail = raw;
      try {
        const parsed = JSON.parse(raw);
        code = parsed?.error?.code ?? parsed?.code ?? "";
        detail =
          parsed?.error?.message ?? parsed?.message ?? parsed?.detail ?? raw;
      } catch {
        /* non-JSON message — use as-is */
      }
      let msg: string;
      switch (code) {
        case "INVALID_CREDENTIALS":
          msg = "用户名或密码错误";
          break;
        case "ACCOUNT_LOCKED":
          msg = `账号已锁定，请稍后再试 (${detail})`;
          break;
        case "USER_DISABLED":
          msg = "账号已被禁用，请联系管理员";
          break;
        case "SESSION_REVOKED":
          msg = "会话已失效，请重新登录";
          break;
        default:
          msg =
            raw.includes("TOKEN") || raw.includes("401")
              ? "用户名或密码错误"
              : detail;
      }
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-sm"
      >
        {/* Brand header */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.1, duration: 0.4 }}
          className="text-center mb-8"
        >
          <div className="flex items-center justify-center gap-3 mb-3">
            <Activity className="h-7 w-7 text-primary" />
            <h1 className="text-2xl font-bold text-text-primary">
              EasyQuant Studio
            </h1>
          </div>
          <p className="text-sm text-text-secondary">
            专业的量化策略开发平台
          </p>
        </motion.div>

        {/* Login card */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.4 }}
        >
          <Card>
            <CardHeader className="text-center pb-2">
              <CardTitle className="text-base">登录</CardTitle>
              <CardDescription>请输入您的账号和密码</CardDescription>
            </CardHeader>
            <CardContent>
              <LoginForm
                onSubmit={handleLogin}
                isLoading={loading}
                error={error}
              />
            </CardContent>
          </Card>
        </motion.div>

        {/* Footer */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5, duration: 0.4 }}
          className="text-center text-xs text-text-muted mt-6"
        >
          EasyQuant — 事件驱动的量化回测框架
        </motion.p>
      </motion.div>
    </div>
  );
}
