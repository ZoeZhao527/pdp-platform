import {
  Activity,
  BookOpen,
  Cpu,
  LayoutDashboard,
  ListChecks,
  MessageSquarePlus,
  RefreshCcw,
  Settings2,
  ShieldCheck,
  Target,
  TerminalSquare,
} from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "./api";
import DevConsole from "./pages/DevConsole";
import ExecutionCenter from "./pages/ExecutionCenter";
import Flywheel from "./pages/Flywheel";
import Guardrails from "./pages/Guardrails";
import InstructionCenter from "./pages/InstructionCenter";
import Knowledge from "./pages/Knowledge";
import Login from "./pages/Login";
import Models from "./pages/Models";
import Overview from "./pages/Overview";
import Settings from "./pages/Settings";
import Strategies from "./pages/Strategies";
import RunLog from "./pages/RunLog";
import type { TenantRow } from "./types";
import { ToastProvider } from "./components/Toast";

type PageKey =
  | "overview"
  | "instructions"
  | "execution"
  | "flywheel"
  | "knowledge"
  | "strategies"
  | "models"
  | "runlog"
  | "guardrails"
  | "dev"
  | "settings";

const NAV: { key: PageKey; label: string; icon: typeof LayoutDashboard }[] = [
  { key: "overview", label: "总览", icon: LayoutDashboard },
  { key: "flywheel", label: "需求飞轮", icon: RefreshCcw },
  { key: "instructions", label: "指令中心", icon: MessageSquarePlus },
  { key: "execution", label: "执行中心", icon: ListChecks },
  { key: "knowledge", label: "知识库", icon: BookOpen },
  { key: "strategies", label: "策略沉淀中心", icon: Target },
  { key: "models", label: "LLM 网关", icon: Cpu },
  { key: "runlog", label: "运行日志", icon: Activity },
  { key: "guardrails", label: "护栏", icon: ShieldCheck },
  { key: "settings", label: "配置", icon: Settings2 },
  { key: "dev", label: "开发者后台", icon: TerminalSquare },
];

export default function App() {
const [authed, setAuthed] = useState(Boolean(localStorage.getItem("pdp_token")));
const [page, setPage] = useState<PageKey>("overview");
const [tenants, setTenants] = useState<TenantRow[]>([]);
const [tenantId, setTenantId] = useState(localStorage.getItem("pdp_tenant_id") || "");

useEffect(() => {
  if (!authed) return;
  const lsTenantId = localStorage.getItem("pdp_tenant_id") || "";
  if (lsTenantId && lsTenantId !== tenantId) setTenantId(lsTenantId);
  api
    .platformTenants()
    .then((rows) => {
      setTenants(rows);
      const current = rows.find((r) => r.id === lsTenantId) || rows[0];
      if (current) {
        localStorage.setItem("pdp_tenant_id", current.id);
        setTenantId(current.id);
      }
        if (current?.industry_id) {
          localStorage.setItem("pdp_industry_id", current.industry_id);
        }
    })
    .catch(() => undefined);
 }, [authed]);

 const switchTenant = (id: string) => {
   const target = tenants.find((r) => r.id === id);
   if (target?.industry_id) {
     localStorage.setItem("pdp_industry_id", target.industry_id);
   }
   // Clear old global chat key + any stale tenant-specific chat keys
   localStorage.removeItem("pdp_chat_messages");
   const _oldTid = localStorage.getItem("pdp_tenant_id");
   if (_oldTid) localStorage.removeItem(`pdp_chat_messages_${_oldTid}`);
   localStorage.setItem("pdp_tenant_id", id);
   setTenantId(id);
   setPage("overview");
 };

const logout = () => {
    localStorage.removeItem("pdp_token");
    localStorage.removeItem("pdp_user");
    localStorage.removeItem("pdp_tenant_id");
    localStorage.removeItem("pdp_industry_id");
    localStorage.removeItem("pdp_chat_messages");
    window.location.reload();
 };

  if (!authed) {
    return <Login onLogin={() => setAuthed(true)} />;
  }

  return (
    <ToastProvider>
    <div className="shell">
      <aside className="sidebar">
       <div className="brand">
          <img src={`${import.meta.env.BASE_URL}logo.svg`} alt="容联云" className="brand-logo" />
         <div>
            <div className="brand-name">消费者运营中台</div>
            <div className="brand-sub">Agent Platform</div>
          </div>
       </div>
       <nav className="nav">
          {NAV.filter((item) => item.key !== "dev" || JSON.parse(localStorage.getItem("pdp_user") || "{}").role === "admin").map((item) => {
            const Icon = item.icon;
            return (
              <button
                type="button"
                key={item.key}
                className={`nav-item ${page === item.key ? "active" : ""}`}
                onClick={() => setPage(item.key)}
              >
                <Icon size={17} strokeWidth={2} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="sidebar-foot">
          <span className="dot" />
          <select className="tenant-select" value={tenantId} onChange={(event) => switchTenant(event.target.value)}>
            {tenants.map((tenant) => (
              <option key={tenant.id} value={tenant.id}>
                {tenant.name}
              </option>
            ))}
          </select>
          <button type="button" className="btn small" onClick={logout}>
            退出
          </button>
        </div>
      </aside>

      <main className="content" key={tenantId}>
        {page === "overview" && <Overview onNavigate={(key: string) => setPage(key as PageKey)} />}
        {page === "instructions" && <InstructionCenter />}
        {page === "execution" && <ExecutionCenter />}
        {page === "flywheel" && <Flywheel onOpenFull={() => setPage("strategies")} />}
        {page === "knowledge" && <Knowledge />}
        {page === "strategies" && <Strategies />}
        {page === "models" && <Models />}
        {page === "runlog" && <RunLog />}
        {page === "guardrails" && <Guardrails />}
        {page === "settings" && <Settings />}
        {page === "dev" && <DevConsole />}
      </main>
    </div>
    </ToastProvider>
  );
}
