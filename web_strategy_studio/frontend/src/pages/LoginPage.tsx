/**
 * LoginPage — register or login for local development.
 * Auto-creates a default user "admin/admin123" on first visit if none exists.
 */
import { useState } from "react";
import { apiJson, setToken } from "../api/client";

interface Props {
  onLogin: () => void;
}

export function LoginPage({ onLogin }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");

  const submit = async () => {
    setError("");
    try {
      if (mode === "register") {
        const resp = await apiJson<{ access_token: string }>(
          "/api/v1/auth/register",
          { method: "POST", body: JSON.stringify({ username, password }) }
        );
        setToken(resp.access_token);
      } else {
        const resp = await apiJson<{ access_token: string }>(
          "/api/v1/auth/login",
          { method: "POST", body: JSON.stringify({ username, password }) }
        );
        setToken(resp.access_token);
      }
      onLogin();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "操作失败");
    }
  };

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100vh",
        background: "var(--bg)",
      }}
    >
      <div
        style={{
          width: 360,
          padding: 24,
          background: "var(--bg-secondary)",
          borderRadius: "var(--radius-md)",
          border: "1px solid var(--border)",
        }}
      >
        <h2 style={{ marginTop: 0, fontSize: 18 }}>EasyQuant Studio</h2>
        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          <button
            onClick={() => setMode("login")}
            style={{
              flex: 1,
              padding: "6px 0",
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: mode === "login" ? "var(--primary)" : "var(--bg)",
              color: mode === "login" ? "#fff" : "var(--text)",
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            登录
          </button>
          <button
            onClick={() => setMode("register")}
            style={{
              flex: 1,
              padding: "6px 0",
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: mode === "register" ? "var(--primary)" : "var(--bg)",
              color: mode === "register" ? "#fff" : "var(--text)",
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            注册
          </button>
        </div>
        {error && (
          <div style={{ color: "var(--state-error)", fontSize: 12, marginBottom: 8 }}>
            {error}
          </div>
        )}
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="用户名"
          style={{
            width: "100%",
            marginBottom: 8,
            padding: 6,
            background: "var(--bg)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-sm)",
            color: "var(--text)",
            fontSize: 13,
            boxSizing: "border-box",
          }}
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="密码"
          onKeyDown={(e) => e.key === "Enter" && submit()}
          style={{
            width: "100%",
            marginBottom: 12,
            padding: 6,
            background: "var(--bg)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-sm)",
            color: "var(--text)",
            fontSize: 13,
            boxSizing: "border-box",
          }}
        />
        <button
          onClick={submit}
          style={{
            width: "100%",
            padding: "8px 0",
            borderRadius: "var(--radius-sm)",
            border: "none",
            background: "var(--primary)",
            color: "#fff",
            fontWeight: 600,
            fontSize: 14,
            cursor: "pointer",
          }}
        >
          {mode === "login" ? "登录" : "注册"}
        </button>
      </div>
    </div>
  );
}
