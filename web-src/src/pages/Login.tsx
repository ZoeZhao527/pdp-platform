import { LogIn } from "lucide-react";
import { useState } from "react";

import { api } from "../api";

export default function Login({ onLogin }: { onLogin: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const submit = async () => {
    setError("");
    try {
      const result = await api.login(username.trim(), password);
      localStorage.setItem("pdp_token", result.token);
      localStorage.setItem("pdp_user", JSON.stringify(result.user));
      localStorage.setItem("pdp_tenant_id", result.user.tenant_id);
      localStorage.setItem("pdp_industry_id", result.industry_id || "");
      onLogin();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="brand-mark">A</div>
        <h1>消费者运营中台</h1>
        <p>请登录后进入系统</p>
        <input
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          placeholder="用户名"
        />
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && submit()}
          placeholder="密码"
        />
        {error && <span className="error-text">{error}</span>}
        <button type="button" className="btn primary" onClick={submit}>
          <LogIn size={16} />
          登录
        </button>
      </div>
    </div>
  );
}
