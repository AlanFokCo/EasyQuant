/**
 * LoginPage — login form for EasyQuant Studio.
 * Registration is disabled; users must be pre-configured by server.
 */
import { useState } from "react";
import { apiJson, setToken } from "../api/client";

interface Props {
  onLogin: () => void;
}

export function LoginPage({ onLogin }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setError("");
    setLoading(true);
    try {
      const resp = await apiJson<{ access_token: string }>(
        "/api/v1/auth/login",
        { method: "POST", body: JSON.stringify({ username, password }) }
      );
      setToken(resp.access_token);
      onLogin();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "登录失败";
      setError(msg.includes("TOKEN") || msg.includes("401") ? "用户名或密码错误" : msg);
    } finally {
      setLoading(false);
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
        {/* Brand */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <polyline
              points="22 12 18 12 15 21 9 3 6 12 2 12"
              stroke="var(--primary)"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <h2 style={{ marginTop: 0, marginBottom: 0, fontSize: 18 }}>EasyQuant Studio</h2>
        </div>

        {error && (
          <div
            role="alert"
            style={{
              color: "var(--state-error)",
              fontSize: 12,
              marginBottom: 12,
              padding: "8px 12px",
              background: "rgba(248,81,73,0.1)",
              borderRadius: "var(--radius-sm)",
            }}
          >
            {error}
          </div>
        )}

        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="用户名"
          disabled={loading}
          autoFocus
          style={{
            width: "100%",
            marginBottom: 8,
            padding: 10,
            background: "var(--bg)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-sm)",
            color: "var(--text)",
            fontSize: 14,
            boxSizing: "border-box",
            opacity: loading ? 0.6 : 1,
          }}
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="密码"
          disabled={loading}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !loading && username && password) {
              submit();
            }
          }}
          style={{
            width: "100%",
            marginBottom: 16,
            padding: 10,
            background: "var(--bg)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-sm)",
            color: "var(--text)",
            fontSize: 14,
            boxSizing: "border-box",
            opacity: loading ? 0.6 : 1,
          }}
        />
        <button
          onClick={submit}
          disabled={loading || !username || !password}
          style={{
            width: "100%",
            padding: "10px 0",
            borderRadius: "var(--radius-sm)",
            border: "none",
            background: loading || !username || !password ? "var(--text-dim)" : "var(--primary)",
            color: "#fff",
            fontWeight: 600,
            fontSize: 14,
            cursor: loading || !username || !password ? "not-allowed" : "pointer",
            transition: "background 0.15s",
          }}
        >
          {loading ? "登录中…" : "登录"}
        </button>
      </div>
    </div>
  );
}