import { useCallback, useEffect, useState } from "react";
import { Building2, BarChart3, ScrollText, Layers, Plus, RefreshCw, Users, ChevronRight, Zap, Eye, EyeOff, CheckCircle2, XCircle, BookOpen, Send, TrendingUp, Cpu } from "lucide-react";

import { api } from "../api";
import type { BrandRow, MeteringRow, AuditLogRow, PlatformAssetOverview, BrandDetail, BrandUserRow, IndustryRow } from "../types";

type Tab = "brands" | "users" | "metering" | "audit" | "assets";

const TABS: { key: Tab; label: string; icon: typeof Building2 }[] = [
  { key: "brands", label: "品牌管理", icon: Building2 },
  { key: "users", label: "用户管理", icon: Users },
  { key: "metering", label: "计量对账", icon: BarChart3 },
  { key: "audit", label: "操作审计", icon: ScrollText },
  { key: "assets", label: "平台资产", icon: Layers },
];

const ROLE_LABELS: Record<string, string> = { admin: "管理员", operator: "运营", viewer: "只读" };

export default function DevConsole() {
  const [tab, setTab] = useState<Tab>("brands");
  const [brands, setBrands] = useState<BrandRow[]>([]);
  const [metering, setMetering] = useState<MeteringRow[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogRow[]>([]);
  const [assets, setAssets] = useState<PlatformAssetOverview | null>(null);
  const [industries, setIndustries] = useState<IndustryRow[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // brand creation
  const [showCreate, setShowCreate] = useState(false);
  const [newBrand, setNewBrand] = useState({ name: "", code: "", industry_id: "" });

  // brand detail drawer
  const [detail, setDetail] = useState<BrandDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // user management
  const [userBrand, setUserBrand] = useState("");
  const [brandUsers, setBrandUsers] = useState<BrandUserRow[]>([]);
  const [showUserCreate, setShowUserCreate] = useState(false);
  const [newUser, setNewUser] = useState({ username: "", password: "", display_name: "", role: "operator" });

  // audit filter
  const [auditFilter, setAuditFilter] = useState({ brandId: "", action: "" });

  const load = useCallback(() => {
    setError("");
    Promise.all([api.devBrands(), api.devMetering(), api.devAuditLogs(), api.devPlatformAssets(), api.platformIndustries()])
      .then(([b, m, a, p, ind]) => {
        setBrands(b);
        setMetering(m);
        setAuditLogs(a);
        setAssets(p);
        setIndustries(ind);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => { load(); }, [load]);

  const createBrand = async () => {
    if (!newBrand.name.trim() || !newBrand.code.trim()) return;
    try {
      const res = await api.devCreateBrand(newBrand.name, newBrand.code, newBrand.industry_id || undefined);
      setNewBrand({ name: "", code: "", industry_id: "" });
      setShowCreate(false);
      const infra = (res as { infra?: Record<string, number> }).infra;
      setNotice(`品牌创建成功，已自动初始化：${infra ? Object.entries(infra).map(([k, v]) => `${k}(${v})`).join(" / ") : "平台级资产已继承"}`);
      load();
      // Auto-open detail to show readiness checklist
      if (res && (res as { id?: string }).id) {
        openDetail((res as { id: string }).id);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const toggleStatus = async (brand: BrandRow) => {
    const next = brand.status === "active" ? "suspended" : "active";
    await api.devUpdateBrandStatus(brand.id, next);
    setNotice(`品牌 ${brand.name} 已${next === "active" ? "启用" : "停用"}`);
    load();
  };

  const openDetail = async (brandId: string) => {
    setDetailLoading(true);
    setDetail(null);
    try {
      const d = await api.devBrandDetail(brandId);
      setDetail(d);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
    setDetailLoading(false);
  };

  const upgradeVersion = async () => {
    try {
      const res = await api.devUpgradePlatformVersion();
      setNotice(`平台版本已升级至 ${res.version}，${res.brands_updated} 个活跃品牌已同步`);
      load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  // user management
  const loadUsers = async (brandId: string) => {
    setUserBrand(brandId);
    try {
      const users = await api.devBrandUsers(brandId);
      setBrandUsers(users);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const createUser = async () => {
    if (!userBrand || !newUser.username.trim() || !newUser.password.trim()) return;
    try {
      await api.devCreateBrandUser(userBrand, newUser);
      setNewUser({ username: "", password: "", display_name: "", role: "operator" });
      setShowUserCreate(false);
      loadUsers(userBrand);
      load();
      setNotice("用户创建成功");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const toggleUser = async (u: BrandUserRow) => {
    await api.devUpdateUser(u.id, { enabled: !u.enabled });
    if (userBrand) loadUsers(userBrand);
    setNotice(`用户 ${u.username} 已${!u.enabled ? "启用" : "停用"}`);
  };

  const changeRole = async (u: BrandUserRow, role: string) => {
    await api.devUpdateUser(u.id, { role });
    if (userBrand) loadUsers(userBrand);
    setNotice(`用户 ${u.username} 角色已改为 ${ROLE_LABELS[role] || role}`);
  };

  const filterAudit = async () => {
    const rows = await api.devAuditLogs(
      auditFilter.brandId || undefined,
      auditFilter.action || undefined,
    );
    setAuditLogs(rows);
  };

  const selectedBrand = brands.find((b) => b.id === userBrand);

  return (
    <>
      {error && <span className="error-text">{error}</span>}
      {notice && <span className="success-text">{notice}</span>}

      <section className="dev-tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`dev-tab${tab === t.key ? " active" : ""}`}
            onClick={() => setTab(t.key)}
          >
            <t.icon size={16} />
            {t.label}
          </button>
        ))}
        <button className="dev-tab refresh" onClick={load}>
          <RefreshCw size={15} />
        </button>
      </section>

      {/* 品牌管理 */}
      {tab === "brands" && (
        <>
          <section className="panel">
            <div className="panel-head">
              <h2>品牌分支</h2>
              <button className="btn primary small" onClick={() => setShowCreate(!showCreate)}>
                <Plus size={15} /> 派生新品牌
              </button>
            </div>
            {showCreate && (
              <div className="simulate-bar">
                <input
                  value={newBrand.name}
                  onChange={(e) => setNewBrand({ ...newBrand, name: e.target.value })}
                  placeholder="品牌名称"
                />
                <input
                  value={newBrand.code}
                  onChange={(e) => setNewBrand({ ...newBrand, code: e.target.value })}
                  placeholder="品牌编码（英文）"
                />
                <select
                  value={newBrand.industry_id}
                  onChange={(e) => setNewBrand({ ...newBrand, industry_id: e.target.value })}
                >
                  <option value="">选择行业（可选）</option>
                  {industries.map((ind) => (
                    <option key={ind.id} value={ind.id}>{ind.name}</option>
                  ))}
                </select>
                <button className="btn primary" onClick={createBrand}>创建</button>
                <button className="btn" onClick={() => setShowCreate(false)}>取消</button>
              </div>
            )}
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>品牌</th>
                    <th>编码</th>
                    <th>状态</th>
                    <th>版本</th>
                    <th>策略</th>
                    <th>消息</th>
                    <th>LLM 调用</th>
                    <th>Token</th>
                    <th>成本</th>
                    <th>用户</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {brands.map((b) => (
                    <tr key={b.id} className="clickable" onClick={() => openDetail(b.id)}>
                      <td className="cell-main">{b.name} <ChevronRight size={12} className="cell-muted" /></td>
                      <td className="cell-muted">{b.code}</td>
                      <td>
                        <span className={`pill ${b.status === "active" ? "open" : "closed"}`}>
                          {b.status === "active" ? "运行中" : "已停用"}
                        </span>
                      </td>
                      <td className="cell-muted">{b.platform_version || "-"}</td>
                      <td>{b.stats.strategies}</td>
                      <td>{b.stats.messages}</td>
                      <td>{b.stats.llm_calls}</td>
                      <td>{b.stats.llm_tokens.toLocaleString()}</td>
                      <td>¥{b.stats.llm_cost.toFixed(2)}</td>
                      <td>{b.stats.users}</td>
                      <td>
                        {b.code !== "default" && (
                          <button
                            className="btn small"
                            onClick={(e) => { e.stopPropagation(); toggleStatus(b); }}
                          >
                            {b.status === "active" ? "停用" : "启用"}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                  {brands.length === 0 && (
                    <tr><td colSpan={11} className="empty">暂无品牌</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          {/* 品牌详情抽屉 */}
          {(detail || detailLoading) && (
            <section className="panel">
              <div className="panel-head">
                <h2>{detail ? `${detail.name} 基础设施` : "加载中..."}</h2>
                <button className="btn small" onClick={() => setDetail(null)}>关闭</button>
              </div>
              {detail && <ReadinessCard detail={detail} industries={industries} />}
              {detail && (
                <div className="dev-detail-grid">
                  <div className="dev-detail-card">
                    <h3>Agent（{detail.agents.length}）</h3>
                    {detail.agents.map((a) => (
                      <div key={a.id} className="dev-detail-row">
                        <span className="cell-main">{a.name}</span>
                        <span className="cell-muted">{a.key}</span>
                        <span className={`pill ${a.enabled ? "open" : "closed"}`}>{a.enabled ? "启用" : "停用"}</span>
                      </div>
                    ))}
                  </div>
                  <div className="dev-detail-card">
                    <h3>渠道（{detail.channels.length}）</h3>
                    {detail.channels.map((c) => (
                      <div key={c.id} className="dev-detail-row">
                        <span className="cell-main">{c.name}</span>
                        <span className="cell-muted">{c.channel_type}</span>
                        <span className={`pill ${c.enabled ? "open" : "closed"}`}>{c.enabled ? "启用" : "停用"}</span>
                      </div>
                    ))}
                  </div>
                  <div className="dev-detail-card">
                    <h3>KPI 指标（{detail.kpis.length}）</h3>
                    {detail.kpis.map((k) => (
                      <div key={k.id} className="dev-detail-row">
                        <span className="cell-main">{k.metric}</span>
                        <span className="cell-muted">{k.week}</span>
                      </div>
                    ))}
                  </div>
                  <div className="dev-detail-card">
                    <h3>LLM 配置（{detail.llm_configs.length}）</h3>
                    {detail.llm_configs.map((c) => (
                      <div key={c.id} className="dev-detail-row">
                        <span className="cell-main">{c.name}</span>
                        <span className="cell-muted">{c.provider} / {c.model}</span>
                      </div>
                    ))}
                  </div>
                  <div className="dev-detail-card">
                    <h3>用户（{detail.users.length}）</h3>
                    {detail.users.map((u) => (
                      <div key={u.id} className="dev-detail-row">
                        <span className="cell-main">{u.username}</span>
                        <span className="pill ops">{ROLE_LABELS[u.role] || u.role}</span>
                      </div>
                    ))}
                    {detail.users.length === 0 && <span className="cell-muted">暂无用户</span>}
                  </div>
                  <div className="dev-detail-card">
                    <h3>Prompt 模板（{detail.prompt_templates.length}）</h3>
                    {detail.prompt_templates.map((t) => (
                      <div key={t.id} className="dev-detail-row">
                        <span className="cell-main">{t.key}</span>
                        <span className="cell-muted">v{t.version}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </section>
          )}
        </>
      )}

      {/* 用户管理 */}
      {tab === "users" && (
        <section className="panel">
          <div className="panel-head">
            <h2>用户管理</h2>
            <div className="simulate-bar" style={{ border: "none", padding: 0 }}>
              <select
                value={userBrand}
                onChange={(e) => loadUsers(e.target.value)}
              >
                <option value="">选择品牌</option>
                {brands.map((b) => (
                  <option key={b.id} value={b.id}>{b.name}</option>
                ))}
              </select>
              {userBrand && (
                <button className="btn primary small" onClick={() => setShowUserCreate(!showUserCreate)}>
                  <Plus size={15} /> 新建用户
                </button>
              )}
            </div>
          </div>
          {showUserCreate && (
            <div className="simulate-bar">
              <input
                value={newUser.username}
                onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
                placeholder="用户名"
              />
              <input
                type="password"
                value={newUser.password}
                onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                placeholder="密码"
              />
              <input
                value={newUser.display_name}
                onChange={(e) => setNewUser({ ...newUser, display_name: e.target.value })}
                placeholder="显示名（可选）"
              />
              <select
                value={newUser.role}
                onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
              >
                <option value="operator">运营</option>
                <option value="admin">管理员</option>
                <option value="viewer">只读</option>
              </select>
              <button className="btn primary" onClick={createUser}>创建</button>
              <button className="btn" onClick={() => setShowUserCreate(false)}>取消</button>
            </div>
          )}
          {selectedBrand ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>用户名</th>
                    <th>显示名</th>
                    <th>角色</th>
                    <th>状态</th>
                    <th>创建时间</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {brandUsers.map((u) => (
                    <tr key={u.id}>
                      <td className="cell-main">{u.username}</td>
                      <td className="cell-muted">{u.display_name || "-"}</td>
                      <td>
                        <select
                          value={u.role}
                          onChange={(e) => changeRole(u, e.target.value)}
                          className="role-select"
                        >
                          <option value="operator">运营</option>
                          <option value="admin">管理员</option>
                          <option value="viewer">只读</option>
                        </select>
                      </td>
                      <td>
                        <span className={`pill ${u.enabled ? "open" : "closed"}`}>
                          {u.enabled ? "启用" : "停用"}
                        </span>
                      </td>
                      <td className="cell-muted">{u.created_at ? new Date(u.created_at).toLocaleString() : "-"}</td>
                      <td>
                        <button className="btn small" onClick={() => toggleUser(u)}>
                          {u.enabled ? <EyeOff size={14} /> : <Eye size={14} />}
                          {u.enabled ? "停用" : "启用"}
                        </button>
                      </td>
                    </tr>
                  ))}
                  {brandUsers.length === 0 && (
                    <tr><td colSpan={6} className="empty">该品牌暂无用户</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="cell-muted" style={{ padding: "24px 0" }}>请选择品牌查看用户</p>
          )}
        </section>
      )}

      {/* 计量对账 */}
      {tab === "metering" && (
        <section className="panel">
          <div className="panel-head">
            <h2>计量对账</h2>
            <span className="cell-muted">按品牌汇总 LLM Token 用量与成本</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>品牌</th>
                  <th>LLM 调用</th>
                  <th>Prompt Token</th>
                  <th>Completion Token</th>
                  <th>总 Token</th>
                  <th>成本</th>
                  <th>平均延迟</th>
                  <th>API 调用</th>
                  <th>任务数</th>
                </tr>
              </thead>
              <tbody>
                {metering.map((m) => (
                  <tr key={m.brand_id}>
                    <td className="cell-main">{m.brand_name}</td>
                    <td>{m.llm_calls}</td>
                    <td>{m.prompt_tokens.toLocaleString()}</td>
                    <td>{m.completion_tokens.toLocaleString()}</td>
                    <td>{m.total_tokens.toLocaleString()}</td>
                    <td>¥{m.llm_cost.toFixed(4)}</td>
                    <td>{m.avg_latency_ms}ms</td>
                    <td>{m.api_calls}</td>
                    <td>{m.tasks}</td>
                  </tr>
                ))}
                {metering.length === 0 && (
                  <tr><td colSpan={9} className="empty">暂无数据</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* 操作审计 */}
      {tab === "audit" && (
        <section className="panel">
          <div className="panel-head">
            <h2>操作审计</h2>
            <div className="simulate-bar" style={{ border: "none", padding: 0 }}>
              <input
                value={auditFilter.brandId}
                onChange={(e) => setAuditFilter({ ...auditFilter, brandId: e.target.value })}
                placeholder="品牌 ID 过滤"
              />
              <input
                value={auditFilter.action}
                onChange={(e) => setAuditFilter({ ...auditFilter, action: e.target.value })}
                placeholder="动作类型"
              />
              <button className="btn small" onClick={filterAudit}>查询</button>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>时间</th>
                  <th>操作人</th>
                  <th>动作</th>
                  <th>对象</th>
                  <th>变更</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.map((log) => (
                  <tr key={log.id}>
                    <td className="cell-muted">
                      {log.created_at ? new Date(log.created_at).toLocaleString() : "-"}
                    </td>
                    <td>{log.actor}</td>
                    <td><span className="pill ops">{log.action}</span></td>
                    <td className="cell-muted">
                      {log.entity_type || "-"}{log.entity_id ? ` / ${log.entity_id.slice(0, 8)}` : ""}
                    </td>
                    <td className="cell-muted">
                      {log.after ? JSON.stringify(log.after).slice(0, 80) : "-"}
                    </td>
                  </tr>
                ))}
                {auditLogs.length === 0 && (
                  <tr><td colSpan={5} className="empty">暂无审计日志</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* 平台资产 */}
      {tab === "assets" && assets && (
        <>
          <section className="metric-row">
            <div className="metric">
              <span className="metric-label">平台级策略</span>
              <span className="metric-value">{assets.strategies.platform}</span>
            </div>
            <div className="metric">
              <span className="metric-label">平台级护栏</span>
              <span className="metric-value">{assets.guardrails.platform}</span>
            </div>
            <div className="metric">
              <span className="metric-label">平台级知识</span>
              <span className="metric-value">{assets.knowledge.platform}</span>
            </div>
            <div className="metric">
              <span className="metric-label">活跃品牌</span>
              <span className="metric-value">{assets.brands}</span>
            </div>
          </section>
          <section className="panel">
            <div className="panel-head">
              <h2>平台版本管理</h2>
              <button className="btn primary small" onClick={upgradeVersion}>
                <Zap size={15} /> 升级平台版本
              </button>
            </div>
            <p className="cell-muted">点击升级后，所有活跃品牌的 platform_version 将统一推送到最新版本（当前目标 2.0）。品牌自动继承平台级策略/护栏/知识资产。</p>
          </section>
          <section className="panel">
            <div className="panel-head">
              <h2>平台级策略</h2>
              <span className="cell-muted">所有品牌默认继承，可被品牌覆盖</span>
            </div>
            <div className="tag-row">
              {assets.strategies.names.map((name, i) => (
                <span key={i} className="pill platform">{name}</span>
              ))}
              {assets.strategies.names.length === 0 && (
                <span className="cell-muted">暂无平台级策略</span>
              )}
            </div>
          </section>
          <section className="panel">
            <div className="panel-head">
              <h2>平台级护栏</h2>
              <span className="cell-muted">所有品牌默认生效的合规规则</span>
            </div>
            <div className="tag-row">
              {assets.guardrails.names.map((name, i) => (
                <span key={i} className="pill platform">{name}</span>
              ))}
              {assets.guardrails.names.length === 0 && (
                <span className="cell-muted">暂无平台级护栏</span>
              )}
            </div>
          </section>
        </>
      )}
    </>
  );
}

function ReadinessCard({
  detail,
  industries,
}: {
  detail: BrandDetail;
  industries: IndustryRow[];
}) {
  const industryName =
    industries.find((i) => i.id === detail.industry_id)?.name ||
    (detail.industry_id ? "已设置" : "未设置");
  const industryOk = Boolean(detail.industry_id);
  const kbOk = detail.knowledge.doc_count > 0;
  const feishuOk = detail.feishu.configured;
  const usersOk = detail.users.length > 0;
  const agentsEnabled = detail.agents.filter((a) => a.enabled).length;
  const channelsEnabled = detail.channels.filter((c) => c.enabled).length;
  const strategiesOk = detail.strategies_count > 0;

  const items = [
    { label: "行业", ok: industryOk, value: industryOk ? industryName : "未配置", icon: Building2 },
    { label: "知识库", ok: kbOk, value: kbOk ? `${detail.knowledge.doc_count} 文档 / ${detail.knowledge.chunk_count} 切片` : "未导入", icon: BookOpen },
    { label: "飞书接入", ok: feishuOk, value: feishuOk ? (detail.feishu.enabled ? "已启用" : "已配置") : "未配置", icon: Send },
    { label: "账号", ok: usersOk, value: usersOk ? `${detail.users.length} 个` : "未创建", icon: Users },
    { label: "策略", ok: strategiesOk, value: strategiesOk ? `${detail.strategies_count} 条` : "暂无", icon: TrendingUp },
    { label: "Agent", ok: agentsEnabled > 0, value: `${agentsEnabled}/${detail.agents.length} 启用`, icon: Zap },
    { label: "渠道", ok: channelsEnabled > 0, value: `${channelsEnabled}/${detail.channels.length} 启用`, icon: Cpu },
  ];

  const readyCount = items.filter((i) => i.ok).length;
  const allReady = readyCount === items.length;

  return (
    <div className="readiness-card" style={{
      display: "flex",
      gap: 16,
      alignItems: "stretch",
      padding: "16px 20px",
      background: "var(--surface-2, #f8f9fa)",
      borderRadius: 10,
      marginBottom: 16,
      border: "1px solid var(--border, #e5e7eb)",
    }}>
      <div style={{ flexShrink: 0, display: "flex", flexDirection: "column", justifyContent: "center", gap: 6, minWidth: 120 }}>
        <span style={{ fontSize: 13, color: "var(--muted, #6b7280)" }}>配置就绪度</span>
        <span style={{ fontSize: 28, fontWeight: 700, color: allReady ? "#16a34a" : "#d97706" }}>
          {readyCount}/{items.length}
        </span>
        <span className={`pill ${allReady ? "open" : "closed"}`} style={{ width: "fit-content" }}>
          {allReady ? "就绪" : "待完善"}
        </span>
      </div>
      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 10 }}>
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.label} style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 12px",
              background: "var(--surface, #fff)",
              borderRadius: 8,
              border: "1px solid var(--border, #e5e7eb)",
            }}>
              <Icon size={16} style={{ color: item.ok ? "#16a34a" : "#9ca3af", flexShrink: 0 }} />
              <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
                <span style={{ fontSize: 12, color: "var(--muted, #6b7280)" }}>{item.label}</span>
                <span style={{ fontSize: 13, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.value}</span>
              </div>
              {item.ok ? (
                <CheckCircle2 size={15} style={{ color: "#16a34a", flexShrink: 0, marginLeft: "auto" }} />
              ) : (
                <XCircle size={15} style={{ color: "#d1d5db", flexShrink: 0, marginLeft: "auto" }} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
