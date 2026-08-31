import { Check, Copy, GitBranch, Pencil, Plus, Sparkles, ThumbsDown, ThumbsUp, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { api } from "../api";
import { isViewer, WriteGate } from "./WriteGate";
import type {
  CandidateRow,
  EffectBreakdown,
  FeedbackEventRow,
  InstructionRow,
  RecommendRow,
  Strategy,
  StrategyTaskItem,
} from "../types";

type Tab = "library" | "candidates" | "recommend" | "mutate";

export default function StrategyCenter() {
  const [tab, setTab] = useState<Tab>("library");
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [tasks, setTasks] = useState<StrategyTaskItem[]>([]);
  const [acceptedInstructions, setAcceptedInstructions] = useState<InstructionRow[]>([]);
  const [form, setForm] = useState({
    title: "", audience: "", hook: "", script: "", task: "", acceptance: "",
    activity_type: "", channels: "", layers: "", sections: "", kpi_metrics: "", cadence: "", cards: "",
  });
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [feedbackEvents, setFeedbackEvents] = useState<FeedbackEventRow[]>([]);
  const [breakdown, setBreakdown] = useState<EffectBreakdown | null>(null);
  const [breakdownStrategyId, setBreakdownStrategyId] = useState<string | null>(null);
  const viewer = isViewer();

  // P2-2 state
  const [candidates, setCandidates] = useState<CandidateRow[]>([]);
  const [recommendations, setRecommendations] = useState<RecommendRow[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [recommendFilter, setRecommendFilter] = useState({ scenario: "", audience: "", channel: "" });
  const [mutateNote, setMutateNote] = useState("");
  const [tagEditId, setTagEditId] = useState<string | null>(null);
  const [tagForm, setTagForm] = useState({ scenario: "", audience: "", channel: "" });

  const load = useCallback(() => {
    Promise.all([api.strategies(), api.strategyTasks(), api.feedbackEvents(), api.listCandidates()])
      .then(([strategyRows, taskRows, feedbackRows, candidateRows]) => {
        setStrategies(strategyRows);
        setTasks(taskRows);
        setFeedbackEvents(feedbackRows);
        setCandidates(candidateRows);
      })
      .catch((err: Error) => setError(err.message));
    api
      .platformInstructions()
      .then((rows) => setAcceptedInstructions(rows.filter((row) => row.status === "已验收")))
      .catch(() => undefined);
  }, []);

  useEffect(load, [load]);

  const doRecommend = useCallback(() => {
    api
      .recommendStrategies(recommendFilter.scenario || undefined, recommendFilter.audience || undefined, recommendFilter.channel || undefined)
      .then(setRecommendations)
      .catch((err: Error) => setError(err.message));
  }, [recommendFilter]);

  useEffect(() => { doRecommend(); }, [doRecommend]);

  const create = async () => {
    if (!form.title.trim()) return;
    await api.createStrategy(form);
    setForm({ title: "", audience: "", hook: "", script: "", task: "", acceptance: "", activity_type: "", channels: "", layers: "", sections: "", kpi_metrics: "", cadence: "", cards: "" });
    load();
  };
  const dispatch = async (id: string) => { await api.dispatchStrategy(id); load(); };
  const toggle = async (id: string) => { await api.toggleStrategyManaged(id); load(); };
  const promote = async (id: string) => { await api.promotePlatform(id); setNotice("已提升为平台级策略"); load(); };
  const override = async (id: string) => { await api.createBrandOverride(id); setNotice("已创建品牌级覆盖副本"); load(); };
  const showBreakdown = async (id: string) => {
    if (breakdownStrategyId === id) { setBreakdown(null); setBreakdownStrategyId(null); return; }
    const data = await api.strategyEffectBreakdown(id);
    setBreakdown(data); setBreakdownStrategyId(id);
  };
  const updateTaskStatus = async (id: string, status: string) => { await api.updateTaskStatus(id, status); load(); };
  const sedimentFromInstruction = async (instruction: InstructionRow) => {
    const result = await api.createStrategyFromInstruction(instruction.id);
    setNotice(`已沉淀为策略：${result.name}`); load();
  };

  // P2-2 actions
  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };
  const doMutate = async () => {
    if (selectedIds.size < 2) { setError("至少选择 2 个策略进行变异"); return; }
    try {
      const result = await api.mutateStrategies([...selectedIds], mutateNote || undefined);
      setNotice(`候选策略已生成：${result.name}`);
      setSelectedIds(new Set());
      setMutateNote("");
      load();
      setTab("candidates");
    } catch (err: unknown) {
      setError(String(err));
    }
  };
  const approveCandidate = async (id: string) => {
    await api.approveCandidate(id);
    setNotice("候选策略已审核通过，进入策略库");
    load();
  };
  const rejectCandidate = async (id: string) => {
    await api.rejectCandidate(id);
    setNotice("候选策略已拒绝");
    load();
  };
  const startTagEdit = (s: Strategy) => {
    setTagEditId(s.id);
    setTagForm({
      scenario: (s.scenario_tags || []).join(", "),
      audience: (s.audience_tags || []).join(", "),
      channel: (s.channel_tags || []).join(", "),
    });
  };
  const saveTags = async (id: string) => {
    const splitTags = (v: string) => v.split(/[,，]/).map((s) => s.trim()).filter(Boolean);
    await api.updateStrategyTags(id, {
      scenario_tags: splitTags(tagForm.scenario),
      audience_tags: splitTags(tagForm.audience),
      channel_tags: splitTags(tagForm.channel),
    });
    setTagEditId(null);
    load();
  };

  const managedCount = strategies.filter((s) => s.managed).length;
  const tabs: { key: Tab; label: string; icon: React.ReactNode; count?: number }[] = [
    { key: "library", label: "策略库", icon: <Copy size={14} />, count: strategies.length },
    { key: "candidates", label: "候选审核", icon: <Sparkles size={14} />, count: candidates.length },
    { key: "recommend", label: "跨行业推荐", icon: <GitBranch size={14} />, count: recommendations.length },
    { key: "mutate", label: "AI变异", icon: <Plus size={14} /> },
  ];

  const tagChips = (s: Strategy) => (
    <div className="tag-row">
      {(s.scenario_tags || []).map((t) => <span key={"sc" + t} className="tag" style={{ background: "#e8f0fe", color: "#1a56c4" }}>{t}</span>)}
      {(s.audience_tags || []).map((t) => <span key={"au" + t} className="tag" style={{ background: "#e6f4ea", color: "#137333" }}>{t}</span>)}
      {(s.channel_tags || []).map((t) => <span key={"ch" + t} className="tag" style={{ background: "#fef7e0", color: "#b06000" }}>{t}</span>)}
    </div>
  );

  return (
    <>
      {error && <span className="error-text">{error}</span>}
      {notice && <span className="success-text">{notice}</span>}
      {/* sub-tab nav */}
      <div className="sub-tab-bar" style={{ display: "flex", gap: 4, marginBottom: 16, borderBottom: "1px solid var(--border, #e0e0e0)" }}>
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            className={"sub-tab" + (tab === t.key ? " active" : "")}
            onClick={() => setTab(t.key)}
            style={{
              padding: "8px 16px", border: "none", background: tab === t.key ? "var(--accent, #2563eb)" : "transparent",
              color: tab === t.key ? "#fff" : "var(--text-muted, #666)", borderRadius: "6px 6px 0 0",
              cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 13, fontWeight: 500,
            }}
          >
            {t.icon}{t.label}
            {t.count !== undefined && <span style={{ opacity: 0.7, fontSize: 11 }}>({t.count})</span>}
          </button>
        ))}
      </div>

      {/* ── TAB: 策略库 ── */}
      {tab === "library" && (
        <>
          <section className="metric-row">
            <div className="metric"><span className="metric-label">沉淀策略</span><span className="metric-value">{strategies.length}</span></div>
            <div className="metric"><span className="metric-label">托管中</span><span className="metric-value">{managedCount}</span></div>
            <div className="metric"><span className="metric-label">可沉淀指令</span><span className="metric-value">{acceptedInstructions.length}</span></div>
          </section>

          <section className="panel">
            <div className="panel-head"><h2>从已验收指令沉淀</h2><span className="cell-muted">验证过的打法一键沉淀成可复用策略卡</span></div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>指令</th><th>验收时间</th><th></th></tr></thead>
                <tbody>
                  {acceptedInstructions.slice(0, 10).map((instruction) => (
                    <tr key={instruction.id}>
                      <td className="cell-main">{instruction.title}</td>
                      <td className="cell-muted">{instruction.created_at ? new Date(instruction.created_at).toLocaleString() : "-"}</td>
                      <td><WriteGate><button type="button" className="btn small" onClick={() => sedimentFromInstruction(instruction)}>沉淀为策略</button></WriteGate></td>
                    </tr>
                  ))}
                  {acceptedInstructions.length === 0 && <tr><td colSpan={3} className="empty">还没有已验收指令可沉淀</td></tr>}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel">
            <div className="panel-head"><h2>沉淀新策略</h2></div>
            <div className="simulate-bar">
              <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="策略标题" />
              <input value={form.audience} onChange={(e) => setForm({ ...form, audience: e.target.value })} placeholder="人群" />
              <input value={form.acceptance} onChange={(e) => setForm({ ...form, acceptance: e.target.value })} placeholder="验收口径" />
              <input value={form.activity_type} onChange={(e) => setForm({ ...form, activity_type: e.target.value })} placeholder="活动类型（如 会员日/裂变）" />
              <input value={form.channels} onChange={(e) => setForm({ ...form, channels: e.target.value })} placeholder="渠道（如 朋友圈,社群,1v1）" />
              <input value={form.layers} onChange={(e) => setForm({ ...form, layers: e.target.value })} placeholder="分层打法（如 潜客,新客,复购）" />
              <input value={form.kpi_metrics} onChange={(e) => setForm({ ...form, kpi_metrics: e.target.value })} placeholder="KPI（如 转化率,GMV,复购率）" />
              <input value={form.cadence} onChange={(e) => setForm({ ...form, cadence: e.target.value })} placeholder="排期（如 每日1条/每周3次）" />
              <input value={form.cards} onChange={(e) => setForm({ ...form, cards: e.target.value })} placeholder="关联货盘（如体验卡,次卡）" />
              <WriteGate><button type="button" className="btn primary" onClick={create}><Plus size={15} />保存策略卡</button></WriteGate>
            </div>
          </section>

          <section className="panel">
            <div className="panel-head"><h2>策略库</h2></div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>策略</th><th>标签</th><th>状态</th><th>效果分</th><th>托管</th><th></th></tr></thead>
                <tbody>
                  {strategies.map((strategy) => (
                    <tr key={strategy.id}>
                      <td className="cell-main">
                        {strategy.is_platform && <span className="pill platform" title="平台级默认">平台</span>}
                        {!strategy.is_platform && strategy.platform_ref && <span className="pill brand" title="品牌覆盖">覆盖</span>}
                        {strategy.name}
                      </td>
                      <td>
                        {tagEditId === strategy.id ? (
                          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                            <input style={{ width: 120, fontSize: 11 }} value={tagForm.scenario} onChange={(e) => setTagForm({ ...tagForm, scenario: e.target.value })} placeholder="场景(逗号分隔)" />
                            <input style={{ width: 120, fontSize: 11 }} value={tagForm.audience} onChange={(e) => setTagForm({ ...tagForm, audience: e.target.value })} placeholder="人群(逗号分隔)" />
                            <input style={{ width: 120, fontSize: 11 }} value={tagForm.channel} onChange={(e) => setTagForm({ ...tagForm, channel: e.target.value })} placeholder="渠道(逗号分隔)" />
                            <div style={{ display: "flex", gap: 4 }}>
                              <button type="button" className="btn small" onClick={() => saveTags(strategy.id)}><Check size={12} /></button>
                              <button type="button" className="btn small" onClick={() => setTagEditId(null)}><X size={12} /></button>
                            </div>
                          </div>
                        ) : (
                          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                            {tagChips(strategy)}
                            <WriteGate><button type="button" className="btn small" style={{ padding: "2px 6px" }} onClick={() => startTagEdit(strategy)} title="编辑标签"><Pencil size={12} /></button></WriteGate>
                          </div>
                        )}
                      </td>
                      <td>{strategy.status}</td>
                      <td>
                        <div className="effect-cell">
                          <span className="effect-score">{strategy.score.toFixed(2)}</span>
                          <span className="effect-detail">{strategy.runs}次 · 胜{strategy.wins} · 反馈{strategy.feedback_count}</span>
                        </div>
                      </td>
                      <td>{strategy.managed ? "是" : "否"}</td>
                      <td>
                        <div className="tag-row">
                          <WriteGate>
                            {!strategy.is_platform && <button type="button" className="btn small" onClick={() => promote(strategy.id)}>提升平台</button>}
                            {strategy.is_platform && <button type="button" className="btn small" onClick={() => override(strategy.id)}>品牌覆盖</button>}
                            <button type="button" className="btn small" onClick={() => dispatch(strategy.id)}>下发</button>
                            <button type="button" className="btn small" onClick={() => toggle(strategy.id)}>{strategy.managed ? "取消托管" : "托管"}</button>
                            <button type="button" className="btn small" onClick={() => showBreakdown(strategy.id)}>分解</button>
                          </WriteGate>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {strategies.length === 0 && <tr><td colSpan={6} className="empty">暂无策略</td></tr>}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel">
            <div className="panel-head"><h2>执行任务</h2></div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>任务</th><th>渠道</th><th>状态</th><th>验收</th></tr></thead>
                <tbody>
                  {tasks.map((task) => (
                    <tr key={task.id}>
                      <td className="cell-main">{task.title}</td>
                      <td>{task.channel || "-"}</td>
                      <td>
                        <select className="task-status-select" value={task.status} disabled={viewer} onChange={(e) => updateTaskStatus(task.id, e.target.value)}>
                          {["待执行", "执行中", "已完成", "已失败"].map((s) => <option key={s} value={s}>{s}</option>)}
                        </select>
                      </td>
                      <td className="cell-muted">{task.acceptance || "-"}</td>
                    </tr>
                  ))}
                  {tasks.length === 0 && <tr><td colSpan={4} className="empty">暂无任务</td></tr>}
                </tbody>
              </table>
            </div>
          </section>

          {breakdown && breakdownStrategyId && (
            <section className="panel">
              <div className="panel-head">
                <h2>效果分解：{breakdown.name}</h2>
                <button type="button" className="btn small" onClick={() => { setBreakdown(null); setBreakdownStrategyId(null); }}>收起</button>
              </div>
              <div className="effect-breakdown">
                <div className="effect-bar-row">
                  <span className="effect-label">KPI 达成 ({Math.round(breakdown.weights.kpi * 100)}%)</span>
                  <div className="effect-bar"><div className="effect-fill kpi" style={{ width: `${Math.round(breakdown.components.kpi_achievement * 100)}%` }} /></div>
                  <span className="effect-num">{(breakdown.components.kpi_achievement * 100).toFixed(0)}%</span>
                </div>
                <div className="effect-bar-row">
                  <span className="effect-label">胜率 ({Math.round(breakdown.weights.win_rate * 100)}%)</span>
                  <div className="effect-bar"><div className="effect-fill win" style={{ width: `${Math.round(breakdown.components.win_rate * 100)}%` }} /></div>
                  <span className="effect-num">{(breakdown.components.win_rate * 100).toFixed(0)}%</span>
                </div>
                <div className="effect-bar-row">
                  <span className="effect-label">反馈信号 ({Math.round(breakdown.weights.feedback * 100)}%)</span>
                  <div className="effect-bar"><div className="effect-fill fb" style={{ width: `${Math.round(breakdown.components.feedback_signal * 100)}%` }} /></div>
                  <span className="effect-num">{(breakdown.components.feedback_signal * 100).toFixed(0)}%</span>
                </div>
                <div className="effect-total">
                  综合效果分：<strong>{breakdown.score.toFixed(2)}</strong>
                  <span className="cell-muted"> · {breakdown.runs} 次执行 · 胜 {breakdown.wins} · 反馈 {breakdown.feedback_count}</span>
                </div>
              </div>
            </section>
          )}

          <section className="panel">
            <div className="panel-head"><h2>效果回流</h2><span className="cell-muted">飞书群消息解析后的运营动作与策略关联</span></div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>时间</th><th>动作</th><th>数量</th><th>关联策略</th><th>内容</th></tr></thead>
                <tbody>
                  {feedbackEvents.map((ev) => (
                    <tr key={ev.id}>
                      <td className="cell-muted">{ev.created_at ? new Date(ev.created_at).toLocaleString() : "-"}</td>
                      <td><span className="pill demand">{ev.action}</span></td>
                      <td>{ev.amount > 0 ? ev.amount : "-"}</td>
                      <td>{ev.strategy_name || <span className="cell-muted">未关联</span>}</td>
                      <td className="cell-muted">{ev.note}</td>
                    </tr>
                  ))}
                  {feedbackEvents.length === 0 && <tr><td colSpan={5} className="empty">暂无反馈事件</td></tr>}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {/* ── TAB: 候选审核 ── */}
      {tab === "candidates" && (
        <section className="panel">
          <div className="panel-head">
            <h2>AI 候选策略审核</h2>
            <span className="cell-muted">变异组合生成的新策略，人工审核通过后进入策略库</span>
          </div>
          {candidates.length === 0 ? (
            <div className="empty" style={{ padding: 32, textAlign: "center" }}>暂无候选策略。到「AI变异」标签选 2+ 策略生成候选。</div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(420px, 1fr))", gap: 12 }}>
              {candidates.map((c) => (
                <div key={c.id} className="card" style={{ padding: 16, border: "1px solid var(--border, #e0e0e0)", borderRadius: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                    <strong style={{ fontSize: 14 }}>{c.name}</strong>
                    <span className={"pill " + (c.candidate_status === "pending" ? "demand" : "brand")} style={{ flexShrink: 0 }}>{c.candidate_status === "pending" ? "待审核" : c.candidate_status}</span>
                  </div>
                  {c.parent_names.length > 0 && (
                    <div className="cell-muted" style={{ fontSize: 12, marginBottom: 8 }}>
                      来源：{c.parent_names.join(" × ")}
                    </div>
                  )}
                  {c.mutation_note && (
                    <div className="cell-muted" style={{ fontSize: 12, marginBottom: 8 }}>{c.mutation_note}</div>
                  )}
                  <div className="tag-row" style={{ marginBottom: 8 }}>
                    {c.scenario_tags.map((t) => <span key={"s" + t} className="tag" style={{ background: "#e8f0fe", color: "#1a56c4" }}>{t}</span>)}
                    {c.audience_tags.map((t) => <span key={"a" + t} className="tag" style={{ background: "#e6f4ea", color: "#137333" }}>{t}</span>)}
                    {c.channel_tags.map((t) => <span key={"c" + t} className="tag" style={{ background: "#fef7e0", color: "#b06000" }}>{t}</span>)}
                  </div>
                  {c.candidate_status === "pending" && (
                    <WriteGate>
                      <div style={{ display: "flex", gap: 8 }}>
                        <button type="button" className="btn primary small" onClick={() => approveCandidate(c.id)}><ThumbsUp size={14} />审核通过</button>
                        <button type="button" className="btn small" onClick={() => rejectCandidate(c.id)}><ThumbsDown size={14} />拒绝</button>
                      </div>
                    </WriteGate>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* ── TAB: 跨行业推荐 ── */}
      {tab === "recommend" && (
        <section className="panel">
          <div className="panel-head">
            <h2>跨行业策略推荐</h2>
            <span className="cell-muted">按场景/人群/渠道标签匹配其他行业验证过的打法</span>
          </div>
          <div className="simulate-bar" style={{ marginBottom: 16 }}>
            <input value={recommendFilter.scenario} onChange={(e) => setRecommendFilter({ ...recommendFilter, scenario: e.target.value })} placeholder="场景（如 种草/逼单/召回）" />
            <input value={recommendFilter.audience} onChange={(e) => setRecommendFilter({ ...recommendFilter, audience: e.target.value })} placeholder="人群（如 新客/老客/沉睡）" />
            <input value={recommendFilter.channel} onChange={(e) => setRecommendFilter({ ...recommendFilter, channel: e.target.value })} placeholder="渠道（如 朋友圈/社群/1v1）" />
          </div>
          {recommendations.length === 0 ? (
            <div className="empty" style={{ padding: 32, textAlign: "center" }}>暂无跨行业推荐。输入场景/人群/渠道标签后自动匹配。</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>策略</th><th>类型</th><th>标签</th><th>相似度</th><th>效果分</th></tr></thead>
                <tbody>
                  {recommendations.map((r) => (
                    <tr key={r.id}>
                      <td className="cell-main">{r.name}</td>
                      <td className="cell-muted">{r.strategy_type}</td>
                      <td>
                        <div className="tag-row">
                          {r.scenario_tags.map((t) => <span key={"s" + t} className="tag" style={{ background: "#e8f0fe", color: "#1a56c4" }}>{t}</span>)}
                          {r.audience_tags.map((t) => <span key={"a" + t} className="tag" style={{ background: "#e6f4ea", color: "#137333" }}>{t}</span>)}
                          {r.channel_tags.map((t) => <span key={"c" + t} className="tag" style={{ background: "#fef7e0", color: "#b06000" }}>{t}</span>)}
                        </div>
                      </td>
                      <td><span className="pill brand">{r.similarity}</span></td>
                      <td>{r.score.toFixed(2)} ({r.runs}次·胜{r.wins})</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {/* ── TAB: AI变异 ── */}
      {tab === "mutate" && (
        <section className="panel">
          <div className="panel-head">
            <h2>AI 策略变异组合</h2>
            <span className="cell-muted">选 2+ 已验证策略，系统自动合并参数和标签，生成候选新策略</span>
          </div>
          <div className="simulate-bar" style={{ marginBottom: 16 }}>
            <input value={mutateNote} onChange={(e) => setMutateNote(e.target.value)} placeholder="变异说明（可选，如 合并种草+召回打法）" style={{ flex: 1 }} />
            <WriteGate>
              <button type="button" className="btn primary" onClick={doMutate} disabled={selectedIds.size < 2}>
                <Sparkles size={15} />生成候选 ({selectedIds.size})
              </button>
            </WriteGate>
          </div>
          {selectedIds.size > 0 && selectedIds.size < 2 && (
            <div className="cell-muted" style={{ fontSize: 12, marginBottom: 8 }}>还需选择 {2 - selectedIds.size} 个策略</div>
          )}
          <div className="table-wrap">
            <table>
              <thead><tr><th style={{ width: 40 }}></th><th>策略</th><th>标签</th><th>效果分</th></tr></thead>
              <tbody>
                {strategies.filter((s) => !s.is_candidate).map((s) => (
                  <tr key={s.id} style={{ background: selectedIds.has(s.id) ? "var(--accent-soft, #f0f6ff)" : undefined }}>
                    <td>
                      <WriteGate>
                        <input type="checkbox" checked={selectedIds.has(s.id)} onChange={() => toggleSelect(s.id)} />
                      </WriteGate>
                    </td>
                    <td className="cell-main">
                      {s.is_platform && <span className="pill platform">平台</span>}
                      {s.name}
                    </td>
                    <td>{tagChips(s)}</td>
                    <td>{s.score.toFixed(2)} ({s.runs}次·胜{s.wins})</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}
