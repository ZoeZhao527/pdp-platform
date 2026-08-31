import { MessageCircle, MessagesSquare, RefreshCcw, ShieldAlert, Sparkles, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { useMemo } from "react";

import { api } from "../api";
import { OnboardingChecklist } from "../components/OnboardingChecklist";
import type { DailyBriefs, FeishuMessageRow, FeishuSummary, IndustryRow, Overview as OverviewData, TenantRow } from "../types";

function Stat({ icon: Icon, label, value, tone }: {
  icon: typeof MessagesSquare;
  label: string;
  value: number;
  tone: "blue" | "green" | "amber" | "red" | "purple";
}) {
  return (
    <div className="stat">
      <div className={`stat-icon ${tone}`}>
        <Icon size={18} />
      </div>
      <div>
        <div className="stat-value">{value}</div>
        <div className="stat-label">{label}</div>
      </div>
    </div>
  );
}

export default function Overview({ onNavigate }: { onNavigate: (key: string) => void }) {
  const [data, setData] = useState<OverviewData | null>(null);
  const [error, setError] = useState("");
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [industries, setIndustries] = useState<IndustryRow[]>([]);

  useEffect(() => {
    api
      .overview()
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    Promise.all([api.platformTenants(), api.platformIndustries()])
      .then(([tRows, iRows]) => {
        setTenants(tRows);
        setIndustries(iRows);
      })
      .catch(() => undefined);
  }, []);

  const currentTenantId = localStorage.getItem("pdp_tenant_id") || "";
  const currentIndustryId = localStorage.getItem("pdp_industry_id") || "";
  const currentTenant = tenants.find((t) => t.id === currentTenantId);
  const currentIndustry = industries.find((i) => i.id === currentIndustryId);

  return (
    <div className="page">
      <OnboardingChecklist onNavigate={(link) => onNavigate(link)} />
      <header className="page-head">
        <div>
          <h1>运营总览</h1>
          <p>
            {currentTenant ? `品牌：${currentTenant.name}` : "未选择品牌"}
            {currentIndustry ? ` · 行业：${currentIndustry.name}` : ""}
          </p>
        </div>
        {error && <span className="error-text">{error}</span>}
      </header>

      {data && (
        <>
          <section className="stat-grid">
            <Stat icon={MessagesSquare} label="会话数" value={data.conversations} tone="blue" />
            <Stat icon={MessageCircle} label="消息数" value={data.messages} tone="purple" />
            <Stat icon={Users} label="需求信号" value={data.signals} tone="green" />
            <Stat icon={RefreshCcw} label="飞轮闭环" value={data.flywheel_cycles} tone="amber" />
            <Stat icon={ShieldAlert} label="护栏命中" value={data.guardrail_hits} tone="red" />
            <Stat icon={Sparkles} label="LLM 调用" value={data.llm_calls} tone="blue" />
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>需求飞轮指标</h2>
            </div>
            <div className="metric-row">
              <div className="metric">
                <span className="metric-label">闭环周期</span>
                <span className="metric-value">{data.flywheel.avg_closed_loop_days} 天</span>
              </div>
              <div className="metric">
                <span className="metric-label">累计命中</span>
                <span className="metric-value">{data.flywheel.total_hit_count}</span>
              </div>
              <div className="metric">
                <span className="metric-label">累计采纳</span>
                <span className="metric-value">{data.flywheel.total_adopted_count}</span>
              </div>
              <div className="metric">
                <span className="metric-label">平均 ROI</span>
                <span className="metric-value">{data.flywheel.avg_roi}%</span>
              </div>
            </div>
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>最近会话</h2>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>会话</th>
                    <th>类型</th>
                    <th>状态</th>
                    <th>时间</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_conversations.map((item) => (
                    <tr key={item.id}>
                      <td className="cell-main">{item.title || item.external_id}</td>
                      <td>
                        <span className={`pill ${item.conversation_type}`}>
                          {item.conversation_type === "cs" ? "外部客服" : "运营 Agent"}
                        </span>
                      </td>
                      <td>{item.status}</td>
                      <td className="cell-muted">{item.created_at ? new Date(item.created_at).toLocaleString() : "-"}</td>
                    </tr>
                  ))}
                  {data.recent_conversations.length === 0 && (
                    <tr>
                      <td colSpan={4} className="empty">
                        还没有会话，去“会话”页模拟一条客户消息
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
        </section>
        <DailyBriefCard />
        <FeishuChatCard />
      </>
    )}
  </div>
 );
}

function DailyBriefCard() {
  const [briefs, setBriefs] = useState<DailyBriefs | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState("");

  const load = () => {
    setLoading(true);
    api
      .feishuDailyBriefs()
      .then(setBriefs)
      .catch(() => undefined)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const trigger = async (type: "morning" | "evening") => {
    setBusy(type);
    try {
      await api.feishuTriggerBrief(type);
      await load();
    } catch {
      // ignore
    } finally {
      setBusy("");
    }
  };

  const morning = briefs?.morning ?? null;
  const evening = briefs?.evening ?? null;
  const tasks = briefs?.pending_tasks ?? [];

  const byChannel = useMemo(() => {
    const map = new Map<string, typeof tasks>();
    for (const t of tasks) {
      const list = map.get(t.channel) ?? [];
      list.push(t);
      map.set(t.channel, list);
    }
    return [...map.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [tasks]);

  return (
    <section className="panel brief-panel">
      <div className="panel-head">
        <h2>每日简报 · 早九晚六</h2>
        <button type="button" className="btn small" onClick={load} disabled={loading}>
          {loading ? "刷新中…" : "刷新"}
        </button>
      </div>
      <p className="brief-hint">飞书机器人仅在 09:00 发任务清单、18:00 发运营日报，其他时间全程静默采集。</p>
      <div className="brief-grid">
        <div className="brief-col">
          <div className="brief-col-head">
            <h3>晨间任务清单 · 09:00</h3>
            <button type="button" className="btn small" onClick={() => trigger("morning")} disabled={busy === "morning"}>
              {busy === "morning" ? "生成中…" : "生成晨间"}
            </button>
          </div>
          {byChannel.length > 0 && (
            <div className="brief-tasks">
              {byChannel.map(([ch, list]) => (
                <div key={ch} className="brief-task-group">
                  <span className="pill strategy">{ch} {list.length}</span>
                  {list.map((t) => (
                    <div key={t.id} className="brief-task-row">
                      <span className="brief-task-time">{t.due_time || "--"}</span>
                      <span className="brief-task-title">{t.title}</span>
                      {t.audience && <span className="brief-task-aud">{t.audience}</span>}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
          {morning ? (
            <pre className="brief-content">{morning.content}</pre>
          ) : (
            <div className="empty">今日尚未生成晨间清单（09:00 自动生成，或点上方按钮手动触发）</div>
          )}
          {morning && (
            <span className={`pill ${morning.sent ? "strategy" : "demand"}`}>
              {morning.sent ? `已发群 · ${morning.sent_at ?? ""}` : "未发送"}
            </span>
          )}
        </div>
        <div className="brief-col">
          <div className="brief-col-head">
            <h3>运营日报 · 18:00</h3>
            <button type="button" className="btn small" onClick={() => trigger("evening")} disabled={busy === "evening"}>
              {busy === "evening" ? "生成中…" : "生成晚报"}
            </button>
          </div>
          {evening ? (
            <pre className="brief-content">{evening.content}</pre>
          ) : (
            <div className="empty">今日尚未生成运营日报（18:00 自动生成，或点上方按钮手动触发）</div>
          )}
          {evening && (
            <span className={`pill ${evening.sent ? "strategy" : "demand"}`}>
              {evening.sent ? `已发群 · ${evening.sent_at ?? ""}` : "未发送"}
            </span>
          )}
        </div>
      </div>
    </section>
  );
}

function FeishuChatCard() {
  const [messages, setMessages] = useState<FeishuMessageRow[]>([]);
  const [summary, setSummary] = useState<FeishuSummary | null>(null);
  const [input, setInput] = useState("");
  const [reply, setReply] = useState("");
  const [loading, setLoading] = useState(false);
  const [showSystem, setShowSystem] = useState(false);

  const loadAll = () => {
    api.feishuMessages(20).then(setMessages).catch(() => undefined);
    api.feishuSummary().then(setSummary).catch(() => undefined);
  };

  const loadAllWithFeedback = async () => {
    setLoading(true);
    try {
      await Promise.all([
        api.feishuMessages(20).then(setMessages),
        api.feishuSummary().then(setSummary),
      ]);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const runCommand = async (text: string) => {
    if (!text.trim()) return;
    setLoading(true);
    setReply("");
    try {
      const result = await api.feishuHandle(text);
      setReply(result.reply);
      await loadAll();
    } catch (err) {
      setReply("指令执行失败：" + (err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const send = async () => {
    if (!input.trim()) return;
    setLoading(true);
    try {
      await api.feishuSend(input);
      setInput("");
      await loadAll();
    } catch (err) {
      setReply("发送失败：" + (err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const humanMsgs = messages.filter((m) => !m.is_system);
  const systemMsgs = messages.filter((m) => m.is_system);
  const actionEntries = summary
    ? Object.entries(summary.action_breakdown).sort((a, b) => b[1] - a[1])
    : [];

  return (
    <section className="panel feishu-panel">
      <div className="panel-head">
        <h2>飞书回传</h2>
        <button type="button" className="btn small" onClick={loadAllWithFeedback} disabled={loading}>
          {loading ? "刷新中…" : "刷新"}
        </button>
      </div>

      <div className="feishu-summary-bar">
        <div className="feishu-stat">
          <span className="feishu-stat-num">{summary?.today_feedback_count ?? 0}</span>
          <span className="feishu-stat-label">今日回传</span>
        </div>
        <div className="feishu-stat">
          <span className="feishu-stat-num">{humanMsgs.length}</span>
          <span className="feishu-stat-label">群消息</span>
        </div>
        <div className="feishu-stat">
          <span className="feishu-stat-num">{actionEntries.length}</span>
          <span className="feishu-stat-label">操作类型</span>
        </div>
        {actionEntries.length > 0 && (
          <div className="feishu-actions-chips">
            {actionEntries.map(([action, count]) => (
              <span key={action} className="tag">{action} {count}</span>
            ))}
          </div>
        )}
      </div>

      <div className="feishu-body">
        <div className="feishu-timeline">
          {humanMsgs.map((m) => (
            <div key={m.message_id} className="feishu-card">
              <div className="feishu-card-head">
                <span className="feishu-card-sender">{m.sender}</span>
                <span className="feishu-card-time">{m.created_at}</span>
                <span className={`pill ${m.msg_type === "卡片" ? "strategy" : "demand"}`}>{m.msg_type}</span>
              </div>
              <p className="feishu-card-text">{m.text}</p>
            </div>
          ))}
          {humanMsgs.length === 0 && <div className="empty">暂无群消息</div>}

          {systemMsgs.length > 0 && (
            <button
              type="button"
              className="btn small feishu-toggle"
              onClick={() => setShowSystem(!showSystem)}
            >
              {showSystem ? "收起" : "展开"}系统通知 ({systemMsgs.length})
            </button>
          )}
          {showSystem &&
            systemMsgs.map((m) => (
              <div key={m.message_id} className="feishu-card feishu-card-system">
                <span className="feishu-card-time">{m.created_at}</span>
                <p className="feishu-card-text muted">{m.text}</p>
              </div>
            ))}
        </div>

        <div className="feishu-side">
          {summary && summary.feedback_items.length > 0 && (
            <div className="feishu-feedback-list">
              <h3>最近解析</h3>
              {summary.feedback_items.map((item, i) => (
                <div key={i} className="feishu-feedback-item">
                  <span className="pill demand">{item.action}</span>
                  {item.amount > 0 && <span className="feishu-fb-amt">{item.amount}</span>}
                  <span className="feishu-fb-note">{item.note}</span>
                </div>
              ))}
            </div>
          )}
          {reply && <div className="feishu-reply">{reply}</div>}
          <div className="feishu-input-bar">
            <input
              className="feishu-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
              placeholder="输入指令，如：回传：今日卖卡12单"
              disabled={loading}
            />
            <button type="button" className="btn primary" onClick={send} disabled={loading}>
              发送
            </button>
          </div>
          <div className="feishu-quick-bar">
            <button type="button" className="btn small" onClick={() => runCommand("回传：今日卖卡8单")} disabled={loading}>
              回传示例
            </button>
            <button type="button" className="btn small" onClick={() => runCommand("查看当前策略")} disabled={loading}>
              获取策略
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
