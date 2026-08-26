import {
  CheckCircle2,
  FileText,
  Play,
  Plus,
  RefreshCcw,
  Send,
  Zap,
} from "lucide-react";
import type { EChartsOption } from "echarts";
import { useCallback, useEffect, useState } from "react";

import { api } from "../api";
import Chart from "../components/Chart";
import type {
  AlertRow,
  ApiExampleRow,
  ApiLogRow,
  AssetPackage,
  ChannelCheckResult,
  Cockpit,
  DataSourceRow,
  DemandProfileRow,
  FlywheelSignal,
  FlywheelStatus,
  IntegrationRow,
  InstructionRow,
  MarketOverview,
  MatchItem,
  ProductCategory,
  ProductItem,
  ReportDetail,
  ReportDocRow,
  SearchResult,
  Strategy,
  Workbench,
} from "../types";

type TabKey =
  | "workbench"
  | "signals"
  | "demands"
  | "supply"
  | "match"
  | "strategies"
  | "cockpit"
  | "integration"
  | "reports";

const TABS: { key: TabKey; label: string }[] = [
  { key: "workbench", label: "工作台" },
  { key: "signals", label: "信号中心" },
  { key: "demands", label: "需求库" },
  { key: "supply", label: "供给库" },
  { key: "match", label: "匹配中心" },
  { key: "strategies", label: "策略中心" },
  { key: "cockpit", label: "数据驾驶舱" },
  { key: "integration", label: "数据与接口" },
  { key: "reports", label: "汇报中心" },
];

function WorkbenchTab() {
  const [data, setData] = useState<Workbench | null>(null);
  const [status, setStatus] = useState<FlywheelStatus | null>(null);
  const [alerts, setAlerts] = useState<AlertRow[]>([]);
  const [tasks, setTasks] = useState<{ id: string; title: string }[]>([]);
  const [instructions, setInstructions] = useState<InstructionRow[]>([]);
  const [industries, setIndustries] = useState<{ id: string; name: string }[]>([]);
  const [instructionForm, setInstructionForm] = useState({ title: "", content: "", industry_id: "" });
  const [selectedAsset, setSelectedAsset] = useState<AssetPackage | null>(null);
  const [feedback, setFeedback] = useState({ task_id: "", action: "成单", amount: "", note: "" });
  const [query, setQuery] = useState("");
  const [searchResult, setSearchResult] = useState<SearchResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api
      .platformWorkbench()
      .then(setData)
      .then(() => api.flywheelStatus().then(setStatus))
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(load, [load]);

  useEffect(() => {
    api
      .platformAlerts()
      .then(setAlerts)
      .catch(() => undefined);
    api
      .strategyTasks()
      .then((rows) => setTasks(rows.map((row) => ({ id: row.id, title: row.title }))))
      .catch(() => undefined);
    api
      .platformInstructions()
      .then(setInstructions)
      .catch(() => undefined);
    api
      .platformIndustries()
      .then((rows) => setIndustries(rows.map((row) => ({ id: row.id, name: row.name }))))
      .catch(() => undefined);
  }, []);

  const loadInstructions = async () => {
    setInstructions(await api.platformInstructions());
  };

  const createInstruction = async () => {
    if (!instructionForm.title.trim() || !instructionForm.content.trim()) return;
    await api.createInstruction({
      title: instructionForm.title,
      content: instructionForm.content,
      industry_id: instructionForm.industry_id || undefined,
    });
    setInstructionForm({ title: "", content: "", industry_id: "" });
    await loadInstructions();
  };

  const instructionAction = async (id: string, action: "generate" | "approve" | "reject" | "accept") => {
    if (action === "generate") await api.generateInstruction(id);
    if (action === "approve") await api.approveInstruction(id);
    if (action === "reject") await api.rejectInstruction(id);
    if (action === "accept") await api.acceptInstruction(id);
    await loadInstructions();
  };

  const submitFeedback = async () => {
    await api.createFeedback({
      task_id: feedback.task_id || undefined,
      action: feedback.action,
      amount: Number(feedback.amount) || 0,
      note: feedback.note || undefined,
    });
    setFeedback({ task_id: "", action: "成单", amount: "", note: "" });
  };

  const search = async () => {
    if (!query.trim()) return;
    setSearchResult(await api.platformSearch(query.trim()));
  };

  const resolve = async (id: string) => {
    await api.resolveAlert(id);
    setAlerts(await api.platformAlerts());
  };

  const runAuto = async () => {
    setBusy(true);
    try {
      await api.runFlywheelAuto(100, false);
      load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const collectNow = async () => {
    setBusy(true);
    try {
      await api.runFlywheelAuto(50, true);
      load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {error && <span className="error-text">{error}</span>}
      <section className="panel">
        <div className="panel-head">
          <h2>全局搜索</h2>
        </div>
        <div className="simulate-bar">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && search()}
            placeholder="搜索信号、策略、任务"
          />
          <button type="button" className="btn primary small" onClick={search}>
            搜索
          </button>
        </div>
        {searchResult && (
          <div className="hit-list compact">
            {[
              ...searchResult.signals.map((item) => ({ ...item, kind: "信号" })),
              ...searchResult.strategies.map((item) => ({ ...item, kind: "策略" })),
              ...searchResult.tasks.map((item) => ({ ...item, kind: "任务" })),
            ].map((item) => (
              <div key={`${item.kind}-${item.id}`} className="hit-item">
                <div className="hit-head">
                  <span className="tag">{item.kind}</span>
                </div>
                <p>{item.content}</p>
              </div>
            ))}
            {searchResult.signals.length + searchResult.strategies.length + searchResult.tasks.length === 0 && (
              <div className="empty">没有匹配结果</div>
            )}
          </div>
        )}
      </section>
      {data && (
        <>
          <section className="stat-grid">
            <div className="stat">
              <div className="stat-icon blue">
                <RefreshCcw size={18} />
              </div>
              <div>
                <div className="stat-value">{data.counts.signals}</div>
                <div className="stat-label">信号</div>
              </div>
            </div>
            <div className="stat">
              <div className="stat-icon green">
                <FileText size={18} />
              </div>
              <div>
                <div className="stat-value">{data.counts.demands}</div>
                <div className="stat-label">需求</div>
              </div>
            </div>
            <div className="stat">
              <div className="stat-icon amber">
                <Zap size={18} />
              </div>
              <div>
                <div className="stat-value">{data.counts.products}</div>
                <div className="stat-label">品项</div>
              </div>
            </div>
            <div className="stat">
              <div className="stat-icon purple">
                <CheckCircle2 size={18} />
              </div>
              <div>
                <div className="stat-value">{data.counts.matches}</div>
                <div className="stat-label">匹配</div>
              </div>
            </div>
            <div className="stat">
              <div className="stat-icon blue">
                <Play size={18} />
              </div>
              <div>
                <div className="stat-value">{data.counts.strategies}</div>
                <div className="stat-label">策略</div>
              </div>
            </div>
            <div className="stat">
              <div className="stat-icon red">
                <Send size={18} />
              </div>
              <div>
                <div className="stat-value">{data.counts.tasks}</div>
                <div className="stat-label">任务</div>
              </div>
            </div>
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>待办与快捷操作</h2>
              <div className="tag-row">
                <button type="button" className="btn primary small" onClick={runAuto} disabled={busy}>
                  <Zap size={14} />
                  一键跑闭环
                </button>
                <button type="button" className="btn small" onClick={collectNow} disabled={busy}>
                  <RefreshCcw size={14} />
                  立即采集热点
                </button>
              </div>
            </div>
            <div className="metric-row">
              <div className="metric">
                <span className="metric-label">待处理信号</span>
                <span className="metric-value">{data.todos.pending_signals}</span>
              </div>
              <div className="metric">
                <span className="metric-label">未解决告警</span>
                <span className="metric-value">{data.todos.unresolved_alerts}</span>
              </div>
              <div className="metric">
                <span className="metric-label">待审批策略</span>
                <span className="metric-value">{data.todos.pending_approvals}</span>
              </div>
              <div className="metric">
                <span className="metric-label">定时自动运行</span>
                <span className="metric-value">{status?.auto_enabled ? "已开启" : "已关闭"}</span>
              </div>
            </div>
            {status?.last_run?.time && (
              <div className="tag-row" style={{ marginTop: 12 }}>
                <span className="tag">最近采集：{status.last_run.time}</span>
                {status.last_run.sources.map((source) => (
                  <span key={source.source} className={`tag ${source.ok ? "" : "pill block"}`}>
                    {source.source} {source.ok ? `+${source.count}` : "失败"}
                  </span>
                ))}
              </div>
            )}
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>指令中心</h2>
            </div>
            <div className="simulate-bar">
              <input
                value={instructionForm.title}
                onChange={(event) => setInstructionForm({ ...instructionForm, title: event.target.value })}
                placeholder="指令标题，如：暑期敏感肌促活"
              />
              <select
                className="task-status-select"
                value={instructionForm.industry_id}
                onChange={(event) => setInstructionForm({ ...instructionForm, industry_id: event.target.value })}
              >
                <option value="">选择行业</option>
                {industries.map((industry) => (
                  <option key={industry.id} value={industry.id}>
                    {industry.name}
                  </option>
                ))}
              </select>
              <button type="button" className="btn primary" onClick={createInstruction}>
                发指令
              </button>
            </div>
            <textarea
              className="batch-input"
              value={instructionForm.content}
              onChange={(event) => setInstructionForm({ ...instructionForm, content: event.target.value })}
              placeholder="指令内容：系统结合信号、货盘、知识库和用户需求，产出活动策划、货盘、销售执行包等策略资产"
              rows={3}
            />
            <div className="table-wrap" style={{ marginTop: 12 }}>
              <table>
                <thead>
                  <tr>
                    <th>指令</th>
                    <th>状态</th>
                    <th>时间</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {instructions.map((instruction) => (
                    <tr key={instruction.id}>
                      <td className="cell-main">{instruction.title}</td>
                      <td>
                        <span className={`pill ${instruction.status}`}>{instruction.status}</span>
                      </td>
                      <td className="cell-muted">
                        {instruction.created_at ? new Date(instruction.created_at).toLocaleString() : "-"}
                      </td>
                      <td>
                        <div className="tag-row">
                          {instruction.status === "待处理" && (
                            <button type="button" className="btn small" onClick={() => instructionAction(instruction.id, "generate")}>
                              生成策略
                            </button>
                          )}
                          {instruction.status === "已产出" && (
                            <>
                              <button type="button" className="btn small" onClick={() => instructionAction(instruction.id, "approve")}>
                                批准
                              </button>
                              <button type="button" className="btn small" onClick={() => instructionAction(instruction.id, "reject")}>
                                驳回
                              </button>
                            </>
                          )}
                          {instruction.status === "已批准" && (
                            <button type="button" className="btn small" onClick={() => instructionAction(instruction.id, "accept")}>
                              验收
                            </button>
                          )}
                          {instruction.asset && (
                            <button type="button" className="btn small" onClick={() => setSelectedAsset(instruction.asset)}>
                              查看资产包
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                  {instructions.length === 0 && (
                    <tr>
                      <td colSpan={4} className="empty">
                        还没有指令
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            {selectedAsset && (
              <div className="asset-package">
                <div className="asset-section">
                  <h3>活动策划</h3>
                  <div className="tag-row">
                   <span className="tag">{selectedAsset.activity_plan.theme}</span>
                    {selectedAsset.activity_plan.types.map((item: any, i: number) => (
                      <span key={i} className="tag">
                        {typeof item === "string" ? item : item?.name || ""}
                      </span>
                    ))}
                  </div>
                  <p className="cell-muted">渠道：{selectedAsset.activity_plan.channels.join("、")}</p>
                  {selectedAsset.activity_details?.summary && (
                    <p className="cell-text">{selectedAsset.activity_details.summary}</p>
                  )}
                  {selectedAsset.activity_details?.calendar && (
                    <div className="cell-block">
                      <span className="cell-label">18 天执行日历</span>
                      <p className="cell-text">{selectedAsset.activity_details.calendar}</p>
                    </div>
                  )}
                </div>
                <div className="asset-section">
                  <h3>货盘</h3>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>品项</th>
                          <th>角色</th>
                          <th>价格</th>
                          <th>目标</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedAsset.product_mix.map((product) => (
                          <tr key={product.name}>
                            <td className="cell-main">{product.name}</td>
                            <td>{product.role}</td>
                            <td>¥{product.price}</td>
                            <td className="cell-muted">{product.target}</td>
                          </tr>
                        ))}
                      </tbody>
                  </table>
                </div>
                {selectedAsset.card_structure && (
                  <>
                    {selectedAsset.card_structure.summary && (
                      <p className="cell-text">{selectedAsset.card_structure.summary}</p>
                    )}
                    {selectedAsset.card_structure.rules && (
                      <div className="cell-block">
                        <span className="cell-label">组合规则</span>
                        <p className="cell-text">{selectedAsset.card_structure.rules}</p>
                      </div>
                    )}
                  </>
                )}
              </div>
                <div className="asset-section">
                  <h3>销售执行包</h3>
                  <div className="tag-row">
                    {selectedAsset.sales_playbook.sections.map((item) => (
                      <span key={item} className="tag">
                        {item}
                      </span>
                    ))}
                  </div>
                  <div className="tag-row">
                    {selectedAsset.sales_playbook.layer_plays.map((item) => (
                      <span key={item.layer} className="tag">
                        {item.layer}：{item.goal}
                      </span>
                    ))}
                  </div>
                  {selectedAsset.script_templates && (
                    <div className="script-grid">
                      {selectedAsset.script_templates.opening && (
                        <div className="cell-block">
                          <span className="cell-label">破冰开场</span>
                          <p className="cell-text">{selectedAsset.script_templates.opening}</p>
                        </div>
                      )}
                      {selectedAsset.script_templates.close && (
                        <div className="cell-block">
                          <span className="cell-label">逼单促成</span>
                          <p className="cell-text">{selectedAsset.script_templates.close}</p>
                        </div>
                      )}
                      {selectedAsset.script_templates.objection && (
                        <div className="cell-block">
                          <span className="cell-label">异议处理</span>
                          <p className="cell-text">{selectedAsset.script_templates.objection}</p>
                        </div>
                      )}
                      {selectedAsset.script_templates.follow_up && (
                        <div className="cell-block">
                          <span className="cell-label">回访跟进</span>
                          <p className="cell-text">{selectedAsset.script_templates.follow_up}</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
                <div className="asset-section">
                  <h3>内容排期</h3>
                  <div className="tag-row">
                    {selectedAsset.content_schedule.schedules.map((item) => (
                      <span key={`${item.channel}-${item.cadence}`} className="tag">
                        {item.channel} · {item.cadence}
                      </span>
                    ))}
                  </div>
                  {selectedAsset.content_materials?.summary && (
                    <p className="cell-text">{selectedAsset.content_materials.summary}</p>
                  )}
                </div>
                <div className="asset-section">
                  <h3>KPI 目标</h3>
                  <div className="tag-row">
                    {selectedAsset.kpi_targets.map((item) => (
                      <span key={item} className="tag">
                        {item}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>告警中心</h2>
              <span className="cell-muted">未解决 {alerts.filter((alert) => !alert.resolved).length}</span>
            </div>
            <div className="hit-list compact">
              {alerts.slice(0, 8).map((alert) => (
                <div key={alert.id} className="hit-item">
                  <div className="hit-head">
                    <span className={`pill ${alert.resolved ? "done" : "block"}`}>
                      {alert.resolved ? "已解决" : alert.alert_type}
                    </span>
                    <span className="cell-muted">
                      {alert.created_at ? new Date(alert.created_at).toLocaleString() : "-"}
                    </span>
                  </div>
                  <p>{alert.message}</p>
                  {!alert.resolved && (
                    <div className="tag-row" style={{ marginTop: 8 }}>
                      <button type="button" className="btn small" onClick={() => resolve(alert.id)}>
                        <CheckCircle2 size={14} />
                        标记解决
                      </button>
                    </div>
                  )}
                </div>
              ))}
              {alerts.length === 0 && <div className="empty">暂无告警</div>}
            </div>
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>效果回写</h2>
            </div>
            <div className="simulate-bar">
              <select
                className="task-status-select"
                value={feedback.task_id}
                onChange={(event) => setFeedback({ ...feedback, task_id: event.target.value })}
              >
                <option value="">选择任务</option>
                {tasks.map((task) => (
                  <option key={task.id} value={task.id}>
                    {task.title}
                  </option>
                ))}
              </select>
              <input
                value={feedback.action}
                onChange={(event) => setFeedback({ ...feedback, action: event.target.value })}
                placeholder="动作，如：成单"
              />
              <input
                value={feedback.amount}
                onChange={(event) => setFeedback({ ...feedback, amount: event.target.value })}
                placeholder="金额"
              />
              <button type="button" className="btn primary" onClick={submitFeedback}>
                回写
              </button>
            </div>
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>KPI 概览</h2>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>指标</th>
                    <th>目标</th>
                    <th>实际</th>
                    <th>周期</th>
                  </tr>
                </thead>
                <tbody>
                  {data.kpi.map((row) => (
                    <tr key={row.metric}>
                      <td className="cell-main">{row.metric}</td>
                      <td>{row.target}</td>
                      <td>{row.actual}</td>
                      <td>{row.week}</td>
                    </tr>
                  ))}
                  {data.kpi.length === 0 && (
                    <tr>
                      <td colSpan={4} className="empty">
                        暂无 KPI
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <div className="split-grid">
            <section className="panel">
              <div className="panel-head">
                <h2>今日动态 · 信号</h2>
              </div>
              <div className="cycle-list">
                {data.recent_signals.map((row) => (
                  <div key={row.id} className="cycle-item">
                    <div className="cycle-head">
                      <span className={`pill ${row.source_type}`}>{row.source_type}</span>
                      <span className={`pill ${row.status}`}>{row.status}</span>
                    </div>
                    <p className="cycle-reply">{row.raw_content}</p>
                  </div>
                ))}
                {data.recent_signals.length === 0 && <div className="empty">暂无信号</div>}
              </div>
            </section>
            <section className="panel">
              <div className="panel-head">
                <h2>今日动态 · 闭环</h2>
              </div>
              <div className="cycle-list">
                {data.recent_executions.map((row) => (
                  <div key={row.id} className="cycle-item">
                    <div className="cycle-head">
                      <span className={`pill ${row.status}`}>{row.status}</span>
                    </div>
                    <p className="cycle-reply">{row.reply || "-"}</p>
                  </div>
                ))}
                {data.recent_executions.length === 0 && <div className="empty">暂无闭环</div>}
              </div>
            </section>
          </div>
        </>
      )}
    </>
  );
}

function SignalsTab() {
  const [rows, setRows] = useState<FlywheelSignal[]>([]);
  const [text, setText] = useState("");
  const [batchText, setBatchText] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api
      .flywheelSignals(80)
      .then(setRows)
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(load, [load]);

  const add = async () => {
    if (!text.trim()) return;
    await api.createFlywheelSignal(text.trim());
    setText("");
    load();
  };

  const batchAdd = async () => {
    const items = batchText
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
    if (items.length === 0) return;
    await api.batchFlywheelSignals(items);
    setBatchText("");
    load();
  };

  const label = async (id: string) => {
    await api.labelFlywheelSignal(id);
    load();
  };

  return (
    <>
      <section className="panel">
        <div className="panel-head">
          <h2>新增信号</h2>
        </div>
        <div className="simulate-bar">
          <input
            value={text}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && add()}
            placeholder="手动录入一条市场或客户需求信号"
          />
          <button type="button" className="btn primary icon-btn" onClick={add} aria-label="新增">
            <Plus size={16} />
          </button>
        </div>
        <textarea
          className="batch-input"
          value={batchText}
          onChange={(event) => setBatchText(event.target.value)}
          placeholder="批量录入信号，一行一条"
          rows={3}
        />
        <button type="button" className="btn small" onClick={batchAdd}>
          批量录入
        </button>
      </section>
      {error && <span className="error-text">{error}</span>}
      <section className="panel">
        <div className="panel-head">
          <h2>信号列表</h2>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>来源</th>
                <th>信号</th>
                <th>状态</th>
                <th>时间</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <span className={`pill ${row.source_type}`}>{row.source_type}</span>
                  </td>
                  <td className="cell-main">{row.raw_content}</td>
                  <td>
                    <span className={`pill ${row.status}`}>{row.status}</span>
                  </td>
                  <td className="cell-muted">
                    {row.created_at ? new Date(row.created_at).toLocaleString() : "-"}
                  </td>
                  <td>
                    {row.status === "new" && (
                      <button type="button" className="btn small" onClick={() => label(row.id)}>
                        打标签
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={5} className="empty">
                    暂无信号
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function DemandsTab() {
  const [rows, setRows] = useState<DemandProfileRow[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api
      .flywheelDemands(80)
      .then(setRows)
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(load, [load]);

  const verify = async (id: string) => {
    await api.verifyDemand(id);
    load();
  };

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>需求画像</h2>
      </div>
      {error && <span className="error-text">{error}</span>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>场景</th>
              <th>标签</th>
              <th>强度</th>
              <th>验证</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const tags = Array.isArray(row.tags) ? row.tags : (row.tags as { tags?: string[] })?.tags ?? [];
              return (
                <tr key={row.id}>
                  <td className="cell-main">{row.scenario}</td>
                  <td>
                    <div className="tag-row">
                      {tags.slice(0, 6).map((tag) => (
                        <span key={tag} className="tag">
                          {tag}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td>{row.intensity}</td>
                  <td>{row.verified ? "已验证" : <button type="button" className="btn small" onClick={() => verify(row.id)}>验证</button>}</td>
                  <td className="cell-muted">
                    {row.created_at ? new Date(row.created_at).toLocaleString() : "-"}
                  </td>
                </tr>
              );
            })}
            {rows.length === 0 && (
              <tr>
                <td colSpan={4} className="empty">
                  暂无需求画像
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SupplyTab({ onGoMatch }: { onGoMatch?: () => void }) {
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [selected, setSelected] = useState<ProductItem | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.flywheelProducts(), api.flywheelProductCategories()])
      .then(([productRows, categoryRows]) => {
        setProducts(productRows);
        setCategories(categoryRows);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <>
      {error && <span className="error-text">{error}</span>}
      <section className="metric-row">
        {categories.map((category) => (
          <div key={category.category} className="metric">
            <span className="metric-label">{category.category}</span>
            <span className="metric-value">{category.count}</span>
          </div>
        ))}
      </section>
      <section className="panel">
        <div className="panel-head">
          <h2>品项供给库</h2>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>品项</th>
                <th>分类</th>
                <th>价格</th>
                <th>功效</th>
                <th>人群</th>
                <th>场景</th>
                <th>主推</th>
              </tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <tr key={product.id} className="clickable-row" onClick={() => setSelected(product)}>
                  <td className="cell-main">{product.name}</td>
                  <td>{product.category || "-"}</td>
                  <td>¥{product.price}</td>
                  <td className="cell-muted">{product.efficacy.slice(0, 4).join("、") || "-"}</td>
                  <td className="cell-muted">{product.segments.slice(0, 3).join("、") || "-"}</td>
                  <td className="cell-muted">{product.seasons.slice(0, 3).join("、") || "-"}</td>
                  <td>{product.is_focus ? "是" : "否"}</td>
                </tr>
              ))}
              {products.length === 0 && (
                <tr>
                  <td colSpan={7} className="empty">
                    暂无品项
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
      {selected && (
        <div className="detail-drawer">
          <div className="detail-drawer-head">
            <h2>{selected.name}</h2>
            <button type="button" className="btn" onClick={() => setSelected(null)}>
              关闭
            </button>
          </div>
          <div className="detail-drawer-body">
            <div className="metric">
              <span className="metric-label">分类 / 价格</span>
              <span className="metric-value">
                {selected.category || "未分类"} · ¥{selected.price}
              </span>
            </div>
            <div className="metric">
              <span className="metric-label">价格带</span>
              <span className="metric-value">{selected.price_band || "-"}</span>
            </div>
            <div className="metric">
              <span className="metric-label">主推</span>
              <span className="metric-value">{selected.is_focus ? "是" : "否"}</span>
            </div>
            <h3>功效</h3>
            <div className="tag-row">
              {selected.efficacy.map((item) => (
                <span key={item} className="tag">
                  {item}
                </span>
              ))}
            </div>
            <h3>人群</h3>
            <div className="tag-row">
              {selected.segments.map((item) => (
                <span key={item} className="tag">
                  {item}
                </span>
              ))}
            </div>
            <h3>场景</h3>
            <div className="tag-row">
              {selected.seasons.map((item) => (
                <span key={item} className="tag">
                  {item}
                </span>
              ))}
            </div>
            <h3>说明</h3>
            <p className="result-text">{selected.description || "暂无说明"}</p>
            <button
              type="button"
              className="btn primary"
              onClick={() => {
                setSelected(null);
                onGoMatch?.();
              }}
            >
              去匹配中心
            </button>
          </div>
        </div>
      )}
    </>
  );
}

function MatchTab() {
  const [rows, setRows] = useState<MatchItem[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api
      .flywheelMatches()
      .then(setRows)
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(load, [load]);

  const run = async () => {
    await api.runFlywheelMatches();
    load();
  };

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>供需匹配</h2>
        <button type="button" className="btn primary small" onClick={run}>
          <Play size={14} />
          运行匹配
        </button>
      </div>
      {error && <span className="error-text">{error}</span>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>需求场景</th>
              <th>品项</th>
              <th>分数</th>
              <th>理由</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td className="cell-main">{row.demand_scenario}</td>
                <td>{row.product_name}</td>
                <td>
                  <span className={`pill ${row.score >= 70 ? "complex" : row.score >= 50 ? "lite" : "block"}`}>
                    {row.score}
                  </span>
                </td>
                <td className="cell-muted">{row.reasons.slice(0, 3).join("；") || "-"}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={4} className="empty">
                  暂无匹配结果
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function StrategyCenterBrief({ onOpenFull }: { onOpenFull?: () => void }) {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .strategies()
      .then(setStrategies)
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <>
      {error && <span className="error-text">{error}</span>}
      <section className="panel">
        <div className="panel-head">
          <h2>策略中心 · 精简视图</h2>
          <button type="button" className="btn primary small" onClick={onOpenFull}>
            前往完整策略中心
          </button>
        </div>
        <div className="metric-row">
          <div className="metric">
            <span className="metric-label">策略总数</span>
            <span className="metric-value">{strategies.length}</span>
          </div>
          <div className="metric">
            <span className="metric-label">托管中</span>
            <span className="metric-value">{strategies.filter((strategy) => strategy.managed).length}</span>
          </div>
          <div className="metric">
            <span className="metric-label">草稿</span>
            <span className="metric-value">
              {strategies.filter((strategy) => strategy.status === "草稿").length}
            </span>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>策略</th>
                <th>类型</th>
                <th>状态</th>
                <th>托管</th>
              </tr>
            </thead>
            <tbody>
              {strategies.slice(0, 6).map((strategy) => (
                <tr key={strategy.id}>
                  <td className="cell-main">{strategy.name}</td>
                  <td>{strategy.strategy_type}</td>
                  <td>{strategy.status}</td>
                  <td>{strategy.managed ? "是" : "否"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function CockpitTab() {
  const [data, setData] = useState<Cockpit | null>(null);
  const [sources, setSources] = useState<DataSourceRow[]>([]);
  const [market, setMarket] = useState<MarketOverview | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.platformCockpit(), api.platformDataSources(), api.marketOverview()])
      .then(([cockpit, sourceRows, marketRows]) => {
        setData(cockpit);
        setSources(sourceRows);
        setMarket(marketRows);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  const sourceOption: EChartsOption = {
    tooltip: {},
    xAxis: { type: "category", data: sources.map((item) => item.source), axisLabel: { interval: 0, rotate: 30 } },
    yAxis: { type: "value" },
    series: [{ type: "bar", data: sources.map((item) => item.count), itemStyle: { color: "#155bd4" } }],
  };

  const executionEntries = Object.entries(data?.execution_status ?? {});
  const executionOption: EChartsOption = {
    tooltip: {},
    series: [
      {
        type: "pie",
        radius: ["38%", "68%"],
        data: executionEntries.map(([name, value]) => ({ name, value })),
      },
    ],
  };

  const platformEntries = Object.entries(market?.platforms ?? {});
  const platformOption: EChartsOption = {
    tooltip: {},
    series: [
      {
        type: "pie",
        radius: ["38%", "68%"],
        data: platformEntries.map(([name, value]) => ({ name, value })),
      },
    ],
  };

  const kpiNames = data?.kpi.map((row) => row.metric) ?? [];
  const kpiOption: EChartsOption = {
    tooltip: {},
    legend: { data: ["目标", "实际"] },
    xAxis: { type: "category", data: kpiNames, axisLabel: { interval: 0, rotate: 25 } },
    yAxis: { type: "value" },
    series: [
      { name: "目标", type: "bar", data: data?.kpi.map((row) => row.target) ?? [] },
      { name: "实际", type: "bar", data: data?.kpi.map((row) => row.actual) ?? [] },
    ],
  };

  return (
    <>
      {error && <span className="error-text">{error}</span>}
      {data && (
        <>
          <section className="metric-row">
            <div className="metric">
              <span className="metric-label">热点信号</span>
              <span className="metric-value">{data.topics}</span>
            </div>
            <div className="metric">
              <span className="metric-label">达人库</span>
              <span className="metric-value">{data.influencers}</span>
            </div>
            {executionEntries.map(([key, value]) => (
              <div key={key} className="metric">
                <span className="metric-label">闭环 · {key}</span>
                <span className="metric-value">{value}</span>
              </div>
            ))}
          </section>

          <section className="chart-grid">
            <section className="panel">
              <div className="panel-head">
                <h2>数据源分布</h2>
              </div>
              <Chart option={sourceOption} />
            </section>
            <section className="panel">
              <div className="panel-head">
                <h2>闭环状态</h2>
              </div>
              <Chart option={executionOption} />
            </section>
            <section className="panel">
              <div className="panel-head">
                <h2>达人平台分布</h2>
              </div>
              <Chart option={platformOption} />
            </section>
            <section className="panel">
              <div className="panel-head">
                <h2>KPI 目标 vs 实际</h2>
              </div>
              <Chart option={kpiOption} />
            </section>
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>热点监听</h2>
            </div>
            <div className="cycle-list">
              {data.hot_topics.map((topic) => (
                <div key={topic.id} className="cycle-item">
                  <div className="cycle-head">
                    <span className={`pill ${topic.status}`}>{topic.status}</span>
                  </div>
                  <p className="cycle-reply">{topic.keyword}</p>
                </div>
              ))}
              {data.hot_topics.length === 0 && <div className="empty">暂无热点</div>}
            </div>
          </section>
        </>
      )}
    </>
  );
}

function IntegrationTab() {
  const [integrations, setIntegrations] = useState<IntegrationRow[]>([]);
  const [sources, setSources] = useState<DataSourceRow[]>([]);
  const [logs, setLogs] = useState<ApiLogRow[]>([]);
  const [examples, setExamples] = useState<ApiExampleRow[]>([]);
  const [subTab, setSubTab] = useState<"platform" | "sources" | "logs" | "examples" | "check">("platform");
  const [checkText, setCheckText] = useState("");
  const [checkResult, setCheckResult] = useState<ChannelCheckResult | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.platformIntegrations(),
      api.platformDataSources(),
      api.platformApiLogs(),
      api.platformApiExamples(),
    ])
      .then(([integrationRows, sourceRows, logRows, exampleRows]) => {
        setIntegrations(integrationRows);
        setSources(sourceRows);
        setLogs(logRows);
        setExamples(exampleRows);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  const runCheck = async () => {
    if (!checkText.trim()) return;
    setCheckResult(await api.checkChannel(checkText.trim()));
  };

  const tabs: { key: typeof subTab; label: string }[] = [
    { key: "platform", label: "接入平台" },
    { key: "sources", label: "数据源状态" },
    { key: "logs", label: "调用日志" },
    { key: "examples", label: "接口示例" },
    { key: "check", label: "质检测试" },
  ];

  return (
    <>
      {error && <span className="error-text">{error}</span>}
      <div className="sub-tabs">
        {tabs.map((tab) => (
          <button
            type="button"
            key={tab.key}
            className={`sub-tab ${subTab === tab.key ? "active" : ""}`}
            onClick={() => setSubTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {subTab === "platform" && (
        <section className="panel">
          <div className="panel-head">
            <h2>接入平台与 API Key</h2>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>名称</th>
                  <th>类型</th>
                  <th>API Key</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {integrations.map((row) => (
                  <tr key={row.id}>
                    <td className="cell-main">{row.name}</td>
                    <td>{row.kind}</td>
                    <td className="cell-muted">{row.api_key ? "已配置" : "未配置"}</td>
                    <td>{row.enabled ? "启用" : "停用"}</td>
                  </tr>
                ))}
                {integrations.length === 0 && (
                  <tr>
                    <td colSpan={4} className="empty">
                      暂无接入平台
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {subTab === "sources" && (
        <section className="panel">
          <div className="panel-head">
            <h2>数据源状态</h2>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>数据源</th>
                  <th>信号数</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((row) => (
                  <tr key={row.source}>
                    <td className="cell-main">{row.source}</td>
                    <td>{row.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {subTab === "logs" && (
        <section className="panel">
          <div className="panel-head">
            <h2>调用日志</h2>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>方法</th>
                  <th>路径</th>
                  <th>状态</th>
                  <th>时间</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((row) => (
                  <tr key={row.id}>
                    <td>{row.method}</td>
                    <td className="cell-main">{row.path}</td>
                    <td>
                      <span className={`pill ${row.status >= 400 ? "block" : "done"}`}>{row.status}</span>
                    </td>
                    <td className="cell-muted">
                      {row.created_at ? new Date(row.created_at).toLocaleString() : "-"}
                    </td>
                  </tr>
                ))}
                {logs.length === 0 && (
                  <tr>
                    <td colSpan={4} className="empty">
                      暂无调用日志
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {subTab === "examples" && (
        <section className="panel">
          <div className="panel-head">
            <h2>接口示例</h2>
          </div>
          <div className="hit-list compact">
            {examples.map((row) => (
              <div key={row.path} className="hit-item">
                <div className="hit-head">
                  <span className="tag">{row.method}</span>
                  <span className="tag">{row.path}</span>
                </div>
                <p>{row.purpose}</p>
                <pre className="json-pre">{row.example}</pre>
              </div>
            ))}
          </div>
        </section>
      )}

      {subTab === "check" && (
        <section className="panel">
          <div className="panel-head">
            <h2>渠道质检测试</h2>
          </div>
          <div className="simulate-bar">
            <input
              value={checkText}
              onChange={(event) => setCheckText(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && runCheck()}
              placeholder="输入要质检的内容"
            />
            <button type="button" className="btn primary" onClick={runCheck}>
              检测
            </button>
          </div>
          {checkResult && (
            <div className="hit-list compact" style={{ marginTop: 12 }}>
              <div className={`hit-item ${checkResult.passed ? "" : ""}`}>
                <div className="hit-head">
                  <span className={`pill ${checkResult.passed ? "done" : "block"}`}>
                    {checkResult.passed ? "通过" : "命中"}
                  </span>
                </div>
                {checkResult.hits.map((hit, index) => (
                  <p key={index}>
                    {hit.source} · {hit.rule} · {hit.keyword} · {hit.action}
                  </p>
                ))}
              </div>
            </div>
          )}
        </section>
      )}
    </>
  );
}

function ReportsTab() {
  const [reports, setReports] = useState<ReportDocRow[]>([]);
  const [detail, setDetail] = useState<ReportDetail | null>(null);
  const [fullscreen, setFullscreen] = useState<ReportDetail | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api
      .platformReports()
      .then(setReports)
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(load, [load]);

  const generate = async () => {
    const result = await api.generateReport();
    load();
    setDetail(await api.getReport(result.id));
  };

  const open = async (id: string) => {
    setDetail(await api.getReport(id));
  };

  return (
    <>
      {error && <span className="error-text">{error}</span>}
      <section className="panel">
        <div className="panel-head">
          <h2>汇报列表</h2>
          <button type="button" className="btn primary small" onClick={generate}>
            <Plus size={14} />
            一键生成汇报
          </button>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>标题</th>
                <th>类型</th>
                <th>时间</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {reports.map((report) => (
                <tr key={report.id}>
                  <td className="cell-main">{report.title}</td>
                  <td>{report.kind}</td>
                  <td className="cell-muted">
                    {report.created_at ? new Date(report.created_at).toLocaleString() : "-"}
                  </td>
                  <td>
                    <div className="tag-row">
                      <button type="button" className="btn small" onClick={() => open(report.id)}>
                        查看
                      </button>
                      <button
                        type="button"
                        className="btn small"
                        onClick={async () => setFullscreen(await api.getReport(report.id))}
                      >
                        全屏演示
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {reports.length === 0 && (
                <tr>
                  <td colSpan={4} className="empty">
                    暂无汇报
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
      {detail && (
        <section className="panel">
          <div className="panel-head">
            <h2>{detail.title}</h2>
          </div>
          <p className="result-text">{detail.content}</p>
        </section>
      )}
      {fullscreen && (
        <div className="fullscreen-report">
          <div className="fullscreen-report-head">
            <h2>{fullscreen.title}</h2>
            <button type="button" className="btn" onClick={() => setFullscreen(null)}>
              关闭
            </button>
          </div>
          <pre className="fullscreen-report-body">{fullscreen.content}</pre>
        </div>
      )}
    </>
  );
}

export default function Flywheel({ onOpenFull }: { onOpenFull?: () => void }) {
  const [tab, setTab] = useState<TabKey>("workbench");

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>C+B 需求飞轮</h1>
          <p>Linkstrate运营中台能力已融入：信号 → 需求 → 供给 → 匹配 → 策略 → 驾驶舱 → 接口 → 汇报</p>
        </div>
      </header>

      <div className="sub-tabs">
        {TABS.map((item) => (
          <button
            type="button"
            key={item.key}
            className={`sub-tab ${tab === item.key ? "active" : ""}`}
            onClick={() => setTab(item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === "workbench" && <WorkbenchTab />}
      {tab === "signals" && <SignalsTab />}
      {tab === "demands" && <DemandsTab />}
      {tab === "supply" && <SupplyTab onGoMatch={() => setTab("match")} />}
      {tab === "match" && <MatchTab />}
      {tab === "strategies" && <StrategyCenterBrief onOpenFull={onOpenFull} />}
      {tab === "cockpit" && <CockpitTab />}
      {tab === "integration" && <IntegrationTab />}
      {tab === "reports" && <ReportsTab />}
    </div>
  );
}
