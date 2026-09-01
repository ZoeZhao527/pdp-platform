import { Bell, CalendarDays, ChevronLeft, ChevronRight, Download, FileText, LayoutGrid, ListChecks, RefreshCcw } from "lucide-react";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { api } from "../api";
import { isViewer, WriteGate } from "../components/WriteGate";
import type { ExecutionCenterData, ExecutionInstructionBoard, ManagedTaskRow, ReportDetail, SendPolicy } from "../types";
import IndustryConfig, { type TabKey as IndustryTab } from "./IndustryConfig";

type TabKey = "overview" | "activity" | "catalog" | "1v1" | "朋友圈" | "社群" | "跟进" | "kpi" | "calendar" | "reports";

const TABS: { key: TabKey; label: string }[] = [
  { key: "overview", label: "概览" },
  { key: "activity", label: "活动" },
  { key: "catalog", label: "货盘" },
  { key: "1v1", label: "1v1" },
  { key: "朋友圈", label: "朋友圈" },
  { key: "社群", label: "社群" },
  { key: "跟进", label: "跟进" },
  { key: "kpi", label: "KPI 与标签" },
  { key: "calendar", label: "排期" },
  { key: "reports", label: "验收报告" },
];

function channelTask(item: ExecutionInstructionBoard, keyword: string) {
  return item.tasks.find((task) => task.channel.includes(keyword));
}

function statusPill(status: string) {
  const tone = status === "已完成" ? "done" : status === "已拦截" || status === "已失败" ? "block" : "";
  return <span className={`pill ${tone}`}>{status}</span>;
}

function InstructionModule({
  item,
  title,
  children,
}: {
  item: ExecutionInstructionBoard;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="exec-card">
      <div className="exec-card-head">
        <div>
          <div className="cell-main">{item.title}</div>
          <div className="cell-muted">{title}</div>
        </div>
        {statusPill(item.status)}
      </div>
      {children}
    </div>
  );
}

function ModulePage({
  templateTab,
  children,
}: {
  templateTab: IndustryTab;
  children: ReactNode;
}) {
  return (
    <div className="module-page">
      <section className="panel module-template-panel">
        <div className="panel-head">
          <h2>模板配置</h2>
          <span className="cell-muted">保存后生效，未发送待办可在排期页点“重算待办”刷新</span>
        </div>
        <IndustryConfig embeddedTab={templateTab} compact />
      </section>
      <section className="panel module-instances-panel">
        <div className="panel-head">
          <h2>执行实例</h2>
        </div>
        {children}
      </section>
    </div>
  );
}

function ChannelBody({
  task,
  onRefresh,
}: {
  task?: ExecutionInstructionBoard["tasks"][number];
  onRefresh?: () => void;
}) {
  if (!task) {
    return <div className="empty">还没有生成该渠道内容</div>;
  }
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState("");
  const sendToFeishu = async () => {
    if (!task || sending) return;
    setSending(true);
    setSendResult("");
    try {
      const res = await api.sendTodoToFeishu(task.id);
      if (res.ok) {
        setSendResult("已发送到飞书群");
      } else {
        setSendResult(res.send_result?.detail || "发送失败");
      }
      onRefresh?.();
    } catch (err) {
      setSendResult("发送失败：" + (err as Error).message);
    } finally {
      setSending(false);
    }
  };
  return (
    <>
      <pre className="exec-content">{task.content}</pre>
      <div className="exec-card-foot">
        <span className="cell-muted">截止：{task.due_at || "-"}</span>
        {task.message_id && <span className="cell-muted">发送 ID：{task.message_id}</span>}
        {task.guardrail && (
          <span className="cell-muted block-text">拦截：{task.guardrail.note}</span>
        )}
        {statusPill(task.status)}
        <button type="button" className="btn small" disabled={sending || task.status === "已下发"} onClick={sendToFeishu} style={{ marginLeft: "auto" }}>
          {sending ? "发送中..." : task.status === "已下发" ? "已发送" : "下发到飞书"}
        </button>
        {sendResult && <span className="cell-muted">{sendResult}</span>}
      </div>
    </>
  );
}

export default function ExecutionCenter() {
  const [data, setData] = useState<ExecutionCenterData | null>(null);
  const [tab, setTab] = useState<TabKey>("overview");
  const [report, setReport] = useState<ReportDetail | null>(null);
  const [error, setError] = useState("");
 const [exporting, setExporting] = useState(false);
 const [feishuTaskId, setFeishuTaskId] = useState<string | null>(null);
 const [feishuMsg, setFeishuMsg] = useState("");

  const load = useCallback(() => {
    api
      .platformExecution()
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, []);

 const sendTaskToFeishu = async (taskId: string) => {
   if (!taskId || feishuTaskId) return;
   setFeishuTaskId(taskId);
   setFeishuMsg("");
   try {
     const res = await api.sendTodoToFeishu(taskId);
     setFeishuMsg(res.ok ? "已发送到飞书群" : (res.send_result?.detail || "发送失败"));
     load();
   } catch (err) {
     setFeishuMsg("发送失败：" + (err as Error).message);
   } finally {
     setFeishuTaskId(null);
   }
 };
 const exportExcel = async () => {
    setExporting(true);
    try {
      await api.exportExecution();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setExporting(false);
    }
  };

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 10000);
    return () => window.clearInterval(timer);
  }, [load]);

  const openReport = async (id: string) => {
    try {
      setReport(await api.platformReport(id));
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const instructions = data?.instructions || [];
  const viewer = isViewer();
  const counts = (data?.tasks || []).reduce<Record<string, number>>((acc, task) => {
    acc[task.status] = (acc[task.status] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>执行中心</h1>
          <p>审批后自动分类展示各板块内容，并自动开始渠道执行</p>
        </div>
        <button type="button" className="btn" onClick={load}>
          <RefreshCcw size={16} /> 刷新
        </button>
        <button type="button" className="btn" disabled={exporting} onClick={exportExcel}>
          <Download size={16} /> {exporting ? "导出中…" : "导出 Excel"}
        </button>
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

      {tab === "overview" && (
        <OverviewBoard data={data} instructions={instructions} counts={counts} />
      )}

      {tab === "activity" && (
        <ModulePage templateTab="activity">
          <div className="exec-grid">
            {instructions.filter((item) => item.asset?.activity_plan).map((item) => (
              <InstructionModule key={item.id} item={item} title="活动策划">
                <div className="tag-row" style={{ marginBottom: 8 }}>
                  {item.asset?.activity_plan.theme && <span className="tag accent">{item.asset.activity_plan.theme}</span>}
                  {item.asset?.activity_plan.goal && <span className="tag">目标：{item.asset.activity_plan.goal}</span>}
                  {item.asset?.activity_plan.budget && <span className="tag">预算：{item.asset.activity_plan.budget}</span>}
                  {(item.asset?.activity_plan.channels || []).map((ch: string, i: number) => (
                    <span key={i} className="tag">{ch}</span>
                  ))}
                </div>
                {(item.asset?.activity_plan.types || []).map((t: any, i: number) => {
                  if (typeof t === "string") return <span key={i} className="tag">{t}</span>;
                  return (
                    <div key={i} className="asset-sub-card">
                      <div className="tag-row" style={{ marginBottom: 6 }}>
                        <span className="tag accent">{t?.name}</span>
                        {t?.mechanism && <span className="tag">玩法：{t.mechanism}</span>}
                        {t?.target_audience && <span className="tag">目标：{t.target_audience}</span>}
                      </div>
                      {t?.products?.length > 0 && (
                        <p className="cell-muted" style={{ marginBottom: 4, fontSize: 12 }}>
                          参与产品：{t.products.join("、")}
                        </p>
                      )}
                      {t?.rhythm?.length > 0 && (
                        <div className="rhythm-grid">
                          {t.rhythm.map((r: any, ri: number) => (
                            <div key={ri} className="rhythm-item">
                              <span className="rhythm-phase">{r.phase}</span>
                              {r.days && <span className="rhythm-days">{r.days}</span>}
                              <p className="cell-text">{r.actions}</p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
                {item.asset?.activity_details?.summary && (
                  <pre className="exec-content">{item.asset.activity_details.summary}</pre>
                )}
              </InstructionModule>
            ))}
            {instructions.filter((item) => item.asset?.activity_plan).length === 0 && (
              <div className="empty panel">还没有生成的活动内容</div>
            )}
          </div>
        </ModulePage>
      )}

      {tab === "catalog" && (
        <ModulePage templateTab="catalog">
          <div className="exec-grid">
           {instructions.filter((item) => (item.asset?.card_structure?.cards?.length || item.asset?.product_mix?.length)).map((item) => (
             <InstructionModule key={item.id} item={item} title="货盘与卡项">
                {(item.asset?.card_structure?.cards || []).length > 0 && (
                  <div style={{ marginBottom: 12 }}>
                    <div className="cell-label" style={{ margin: "4px 0" }}>组卡方案</div>
                    {(item.asset?.card_structure?.cards || []).map((card: any, ci: number) => (
                      <div key={ci} className="cell-block" style={{ marginBottom: 8, padding: 8, border: "1px solid #e0e0e6", borderRadius: 6 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                          <span style={{ fontWeight: 600, fontSize: 14 }}>{card.card_type} · {card.card_name}</span>
                          <span style={{ fontSize: 12, color: card.compliance?.includes("合规") ? "#16a34a" : "#dc2626" }}>
                            {card.compliance || ""}
                          </span>
                        </div>
                        {(card.zones || []).map((zone: any, zi: number) => (
                          <div key={zi} style={{ display: "flex", gap: 4, marginBottom: 4, fontSize: 13 }}>
                            <span style={{ minWidth: 50, color: "#6b7280" }}>{zone.zone}({zone.tier}档)</span>
                            <span style={{ flex: 1 }}>{(zone.items || []).map((it: any) => it.name).join(" / ")}</span>
                            <span style={{ color: "#6b7280" }}>{zone.pick_rule}</span>
                          </div>
                        ))}
                        <div style={{ display: "flex", gap: 16, marginTop: 6, fontSize: 13, fontWeight: 500 }}>
                          <span>门市价: {card.total_retail}元</span>
                          <span>定价: {card.selling_price}元</span>
                          <span style={{ color: "#2563eb" }}>折扣: {card.discount}</span>
                        </div>
                        {card.selling_point && (
                          <p className="cell-text" style={{ marginTop: 4, fontSize: 12 }}>{card.selling_point}</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                {item.asset?.card_structure?.items?.length ? (
                  <div className="table-wrap" style={{ marginBottom: 8 }}>
                    <div className="cell-label" style={{ margin: "4px 0" }}>卡项结构</div>
                    <table>
                      <thead>
                        <tr>
                          <th>卡项</th>
                          <th>价格</th>
                          <th>角色</th>
                          <th>目标人群</th>
                          <th>卖点</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(item.asset.card_structure.items || []).map((card: any, i: number) => (
                          <tr key={i}>
                            <td className="cell-main">{card.name}</td>
                            <td>{card.price}</td>
                            <td>{card.role}</td>
                            <td className="cell-muted">{card.target}</td>
                            <td className="cell-text">{card.selling_point}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : item.asset?.card_structure?.summary && (
                  <pre className="exec-content">{item.asset.card_structure.summary}</pre>
                )}
                {item.asset?.card_structure?.rules && (
                  <div className="cell-block" style={{ marginBottom: 8 }}>
                    <span className="cell-label">组合规则</span>
                    <p className="cell-text">{item.asset.card_structure.rules}</p>
                  </div>
                )}
                {item.asset?.product_mix?.length ? (
                  <>
                    <div className="cell-label" style={{ margin: "4px 0" }}>产品货盘</div>
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>品项</th>
                            <th>角色</th>
                            <th>价格</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(item.asset.product_mix || []).map((product) => (
                            <tr key={product.name}>
                              <td className="cell-main">{product.name}</td>
                              <td>{product.role}</td>
                              <td>¥{product.price}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : null}
             </InstructionModule>
           ))}
           {instructions.filter((item) => (item.asset?.card_structure?.cards?.length || item.asset?.product_mix?.length)).length === 0 && (
             <div className="empty panel">还没有生成的货盘内容</div>
           )}
          </div>
        </ModulePage>
      )}

      {(["1v1", "朋友圈", "社群", "跟进"] as TabKey[]).includes(tab) && (
        <ModulePage templateTab={tab === "1v1" ? "sales" : "content"}>
          <div className="exec-grid">
            {instructions.map((item) => (
              <InstructionModule key={item.id} item={item} title={TABS.find((t) => t.key === tab)?.label || ""}>
                {tab === "1v1" && item.asset?.script_templates ? (
                  <>
                    {item.asset.script_templates.opening && (
                      <div className="cell-block" style={{ marginBottom: 6 }}>
                        <span className="cell-label">通用开场白</span>
                        <p className="cell-text">{item.asset.script_templates.opening}</p>
                      </div>
                    )}
                    {item.asset.script_templates.close && (
                      <div className="cell-block" style={{ marginBottom: 6 }}>
                        <span className="cell-label">通用逼单</span>
                        <p className="cell-text">{item.asset.script_templates.close}</p>
                      </div>
                    )}
                    {item.asset.script_templates.follow_up && (
                      <div className="cell-block" style={{ marginBottom: 8 }}>
                        <span className="cell-label">通用回访</span>
                        <p className="cell-text">{item.asset.script_templates.follow_up}</p>
                      </div>
                    )}
                    {item.asset.script_templates.layered_scripts?.length ? (
                    <div className="layered-scripts-grid">
                      {item.asset.script_templates.layered_scripts.map((ls, i) => (
                        <div key={i} className="layered-script-card">
                          <span className="tag accent">{ls.layer}</span>
                          {ls.opening && (
                            <div className="cell-block" style={{ marginTop: 4 }}>
                              <span className="cell-label">开场白</span>
                              <p className="cell-text">{ls.opening}</p>
                            </div>
                          )}
                          {ls.close && (
                            <div className="cell-block" style={{ marginTop: 4 }}>
                              <span className="cell-label">逼单</span>
                              <p className="cell-text">{ls.close}</p>
                            </div>
                          )}
                          {ls.follow_up && (
                            <div className="cell-block" style={{ marginTop: 4 }}>
                              <span className="cell-label">回访</span>
                              <p className="cell-text">{ls.follow_up}</p>
                            </div>
                          )}
                        </div>
                      ))}
                   </div>
                    ) : null}
                    {item.asset.script_templates.objection_handling?.length ? (
                     <div style={{ marginTop: 8 }}>
                       <span className="cell-label">异议处理（分场景）</span>
                        {item.asset.script_templates.objection_handling.map((oh, i) => (
                          <div key={i} className="cell-block" style={{ marginBottom: 6 }}>
                            <div className="tag-row" style={{ marginBottom: 2 }}>
                              {oh.category && <span className="tag accent">{oh.category}</span>}
                              <span className="cell-label">{oh.scenario}</span>
                            </div>
                            <p className="cell-text">{oh.response}</p>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </>
                ) : (tab === "朋友圈" || tab === "社群") && item.asset?.content_schedule?.daily_content?.length ? (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>日期</th>
                          <th>渠道</th>
                          <th>内容</th>
                        </tr>
                      </thead>
                      <tbody>
                        {item.asset.content_schedule.daily_content
                          .filter((d) => (tab === "朋友圈" ? d.channel.includes("朋友圈") : d.channel.includes("社群")))
                          .map((d, i) => (
                            <tr key={i}>
                              <td className="cell-main">{d.day}</td>
                              <td>{d.channel}</td>
                              <td>{d.content}</td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                 <ChannelBody task={channelTask(item, tab)} onRefresh={load} />
                )}
                {channelTask(item, tab) && (
                  <div className="exec-card-foot" style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    {statusPill(channelTask(item, tab)!.status)}
                    {channelTask(item, tab)!.due_at && (
                      <span className="cell-muted">截止：{channelTask(item, tab)!.due_at}</span>
                    )}
                    <WriteGate>
                      <button type="button" className="btn small primary"
                        disabled={!!feishuTaskId || channelTask(item, tab)!.status === "已下发"}
                        onClick={() => sendTaskToFeishu(channelTask(item, tab)!.id)}
                        style={{ marginLeft: "auto" }}>
                        {feishuTaskId === channelTask(item, tab)!.id ? "发送中..." : channelTask(item, tab)!.status === "已下发" ? "已发送" : "下发到飞书"}
                      </button>
                    </WriteGate>
                    {feishuMsg && true && (
                      <span className="cell-muted">{feishuMsg}</span>
                    )}
                  </div>
                )}
              </InstructionModule>
            ))}
            {instructions.length === 0 && <div className="empty panel">还没有指令</div>}
          </div>
        </ModulePage>
      )}

      {tab === "kpi" && (
        <ModulePage templateTab="kpi">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>指令</th>
                  <th>状态</th>
                  <th>KPI 目标</th>
                  <th>回填结果</th>
                </tr>
              </thead>
              <tbody>
                {instructions.map((item) => {
                  const targets = item.asset?.kpi_targets || [];
                  const results = item.kpi_results || {};
                  return (
                    <tr key={item.id}>
                      <td className="cell-main">{item.title}</td>
                      <td>{statusPill(item.status)}</td>
                      <td className="cell-muted">
                        {targets.length
                          ? targets
                              .map((metric) =>
                                metric === "GMV" && item.goal_value ? `${metric} ${item.goal_value}` : metric,
                              )
                              .join("、")
                          : "-"}
                      </td>
                      <td>
                        {Object.keys(results).length ? (
                          <div className="tag-row">
                            {Object.entries(results).map(([key, value]) => (
                              <span key={key} className="tag">
                                {key}: {String(value)}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="cell-muted">待回填</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
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
        </ModulePage>
      )}

      {tab === "calendar" && (
        <div className="page-stack">
          <SendPolicyPanel instructions={instructions} onRefresh={load} viewer={viewer} />
          <CalendarView
            instructions={instructions}
            managedTasks={data?.managed_tasks || []}
            onRefresh={load}
            viewer={viewer}
          />
        </div>
      )}

      {tab === "reports" && (
        <section className="panel">
          <div className="panel-head">
            <h2>
              <FileText size={16} /> 验收报告
            </h2>
            <span className="cell-muted">{data?.reports.length || 0} 份</span>
          </div>
          <div className="report-list">
            {(data?.reports || []).map((row) => (
              <div key={row.id} className="report-item">
                <div>
                  <div className="cell-main">{row.title}</div>
                  <div className="cell-muted">{row.created_at || "-"}</div>
                </div>
                <button type="button" className="btn small" onClick={() => openReport(row.id)}>
                  查看
                </button>
              </div>
            ))}
            {(data?.reports || []).length === 0 && <div className="empty">还没有验收报告</div>}
          </div>
        </section>
      )}

      {report && (
        <div className="asset-overlay">
          <div className="asset-overlay-head">
            <h2>{report.title}</h2>
            <button type="button" className="btn small" onClick={() => setReport(null)}>
              关闭
            </button>
          </div>
          <div className="asset-overlay-body">
            <div className="asset-package">
              <pre className="report-content">{report.content}</pre>
            </div>
          </div>
        </div>
      )}
      {error && <p className="error-text">{error}</p>}
    </div>
  );
}

function OverviewBoard({
  data,
  instructions,
  counts,
}: {
  data: ExecutionCenterData | null;
  instructions: ExecutionInstructionBoard[];
  counts: Record<string, number>;
}) {
  const pendingApproval = instructions.filter((item) => item.status === "已产出").length;
  const accepted = instructions.filter((item) => item.status === "已验收").length;
  const metrics = [
    { label: "待审批指令", value: pendingApproval },
    { label: "执行中任务", value: counts["执行中"] || 0 },
    { label: "已完成任务", value: counts["已完成"] || 0 },
    { label: "拦截任务", value: counts["已拦截"] || 0 },
    { label: "已验收指令", value: accepted },
    { label: "验收报告", value: data?.reports.length || 0 },
    { label: "跟进提醒", value: data?.alerts.length || 0 },
  ];
  return (
    <div className="page-stack">
      <section className="metric-row">
        {metrics.map((item) => (
          <div className="metric" key={item.label}>
            <span className="metric-label">{item.label}</span>
            <span className="metric-value">{item.value}</span>
          </div>
        ))}
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>
            <LayoutGrid size={16} /> 最近指令
          </h2>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>指令</th>
                <th>状态</th>
                <th>渠道任务</th>
              </tr>
            </thead>
            <tbody>
              {instructions.slice(0, 10).map((item) => (
                <tr key={item.id}>
                  <td className="cell-main">{item.title}</td>
                  <td>{statusPill(item.status)}</td>
                  <td className="cell-muted">
                    {item.tasks.length
                      ? item.tasks.map((task) => task.status).join(" / ")
                      : "尚未审批"}
                  </td>
                </tr>
              ))}
              {instructions.length === 0 && (
                <tr>
                  <td colSpan={3} className="empty">
                    还没有指令
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>
            <ListChecks size={16} /> 托管策略任务
          </h2>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>策略</th>
                <th>渠道</th>
                <th>状态</th>
                <th>发送 ID</th>
              </tr>
            </thead>
            <tbody>
              {(data?.managed_tasks || []).slice(0, 10).map((task) => (
                <tr key={task.id}>
                  <td className="cell-main">{task.title}</td>
                  <td>{task.channel}</td>
                  <td>{statusPill(task.status)}</td>
                  <td className="cell-muted">{task.message_id || "-"}</td>
                </tr>
              ))}
              {(data?.managed_tasks || []).length === 0 && (
                <tr>
                  <td colSpan={4} className="empty">
                    暂无托管策略任务
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>
            <Bell size={16} /> 跟进与拦截提醒
          </h2>
        </div>
        <div className="hit-list compact">
          {(data?.alerts || []).slice(0, 8).map((alert) => (
            <div key={alert.id} className="hit-item">
              <div className="hit-head">
                <span className={`pill ${alert.resolved ? "done" : "block"}`}>{alert.alert_type}</span>
                <span className="cell-muted">{alert.created_at || "-"}</span>
              </div>
              <p className="hit-text">{alert.message}</p>
            </div>
          ))}
          {(data?.alerts || []).length === 0 && <div className="empty">暂无提醒</div>}
        </div>
      </section>
    </div>
  );
}

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];

interface CalendarItem {
  id?: string;
  kind: "task" | "todo";
  channel: string;
  label: string;
  time?: string;
  snippet: string;
  status?: string;
  due_at?: string;
  due_time?: string;
  todo?: boolean;
}

function pad2(value: number) {
  return String(value).padStart(2, "0");
}

function dateKey(date: Date) {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

function shortChannel(channel: string) {
  if (channel.includes("1v1")) return "1v1";
  if (channel.includes("朋友圈")) return "朋友圈";
  if (channel.includes("社群")) return "社群";
  if (channel.includes("跟进")) return "跟进";
  return channel;
}

function buildCalendarItems(
  instructions: ExecutionInstructionBoard[],
  managedTasks: ManagedTaskRow[],
  year: number,
  month: number,
): Record<string, CalendarItem[]> {
  const itemsByDate: Record<string, CalendarItem[]> = {};

  for (const instruction of instructions) {
    for (const task of instruction.tasks) {
      if (!task.due_at) continue;
      const date = new Date(`${task.due_at}T00:00:00`);
      if (date.getFullYear() !== year || date.getMonth() !== month) continue;
      const key = dateKey(date);
      (itemsByDate[key] ||= []).push({
        id: task.id,
        kind: task.todo ? "todo" : "task",
        channel: shortChannel(task.channel),
        label: task.title.replace(`${instruction.title}·`, ""),
        time: task.due_time || "",
        snippet: task.content,
        status: task.status,
        due_at: task.due_at,
        due_time: task.due_time,
        todo: Boolean(task.todo),
      });
    }
  }
  for (const task of managedTasks) {
    if (!task.due_at || !task.todo) continue;
    const date = new Date(`${task.due_at}T00:00:00`);
    if (date.getFullYear() !== year || date.getMonth() !== month) continue;
    const key = dateKey(date);
    (itemsByDate[key] ||= []).push({
      id: task.id,
      kind: "todo",
      channel: shortChannel(task.channel),
      label: task.title,
      time: task.due_time || "",
      snippet: task.content,
      status: task.status,
      due_at: task.due_at,
      due_time: task.due_time,
      todo: true,
    });
  }
  return itemsByDate;
}

const CHANNEL_LIMIT_KEYS = ["1v1", "朋友圈", "社群", "跟进"];

function SendPolicyPanel({
  instructions,
  onRefresh,
  viewer,
}: {
  instructions: ExecutionInstructionBoard[];
  onRefresh: () => void;
  viewer: boolean;
}) {
  const [policy, setPolicy] = useState<SendPolicy | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .sendPolicy()
      .then(setPolicy)
      .catch((err: Error) => setError(err.message));
  }, []);

  const update = (patch: Partial<SendPolicy>) => {
    if (policy) setPolicy({ ...policy, ...patch });
  };

  const save = async () => {
    if (!policy) return;
    setBusy(true);
    try {
      setPolicy(await api.updateSendPolicy(policy));
      onRefresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const togglePause = async (id: string) => {
    setBusy(true);
    try {
      await api.toggleInstructionPlanPause(id);
      onRefresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (!policy) {
    return (
      <section className="panel">
        <div className="empty">加载发送策略中…</div>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>发送策略</h2>
        <WriteGate>
          <button type="button" className="btn small" disabled={busy} onClick={save}>
            保存策略
          </button>
        </WriteGate>
      </div>
      <div className="send-policy-grid">
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={policy.auto_enabled}
            disabled={viewer}
            onChange={(event) => update({ auto_enabled: event.target.checked })}
          />
          自动下发
        </label>
        <label className="field">
          <span>每日时间窗</span>
          <div className="time-range">
            <input
              type="time"
              value={policy.window_start}
              disabled={viewer}
              onChange={(event) => update({ window_start: event.target.value })}
            />
            至
            <input
              type="time"
              value={policy.window_end}
              disabled={viewer}
              onChange={(event) => update({ window_end: event.target.value })}
            />
          </div>
        </label>
        <label className="field">
          <span>补发窗口（小时）</span>
          <input
            type="number"
            min={0}
            value={policy.grace_hours}
            disabled={viewer}
            onChange={(event) => update({ grace_hours: Number(event.target.value) })}
          />
        </label>
        {CHANNEL_LIMIT_KEYS.map((key) => (
          <label className="field" key={key}>
            <span>{key} 每日上限</span>
            <input
              type="number"
              min={0}
              value={policy.max_per_day[key] ?? 0}
              disabled={viewer}
              onChange={(event) =>
                update({ max_per_day: { ...policy.max_per_day, [key]: Number(event.target.value) } })
              }
            />
          </label>
        ))}
        <div className="channel-pause">
          <span>暂停渠道</span>
          <div className="tag-row">
            {CHANNEL_LIMIT_KEYS.map((key) => (
              <label key={key} className="check-chip">
                <input
                  type="checkbox"
                  checked={policy.paused_channels.includes(key)}
                  disabled={viewer}
                  onChange={(event) => {
                    const next = new Set(policy.paused_channels);
                    if (event.target.checked) next.add(key);
                    else next.delete(key);
                    update({ paused_channels: [...next] });
                  }}
                />
                {key}
              </label>
            ))}
          </div>
        </div>
      </div>
      <div className="instruction-pause">
        <span className="cell-muted">整月暂停/恢复（按指令）</span>
        <div className="tag-row">
          {instructions
            .filter((item) => item.tasks.some((task) => task.todo))
            .map((item) => (
              <button
                type="button"
                key={item.id}
                className={`pause-chip ${item.plan_paused ? "active" : ""}`}
                disabled={busy || viewer}
                onClick={() => togglePause(item.id)}
              >
                {item.plan_paused ? "已暂停" : "执行中"} · {item.title}
              </button>
            ))}
          {instructions.filter((item) => item.tasks.some((task) => task.todo)).length === 0 && (
            <span className="cell-muted">还没有生成排期待办</span>
          )}
        </div>
      </div>
      {error && <p className="error-text">{error}</p>}
    </section>
  );
}

interface TodoDraft {
  due_at: string;
  due_time: string;
  content: string;
  status: string;
}

function CalendarView({
  instructions,
  managedTasks,
  onRefresh,
  viewer,
}: {
  instructions: ExecutionInstructionBoard[];
  managedTasks: ManagedTaskRow[];
  onRefresh: () => void;
  viewer: boolean;
}) {
  const now = new Date();
  const [monthOffset, setMonthOffset] = useState(0);
  const [editing, setEditing] = useState<CalendarItem | null>(null);
  const [draft, setDraft] = useState<TodoDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [editError, setEditError] = useState("");
  const base = new Date(now.getFullYear(), now.getMonth() + monthOffset, 1);
  const year = base.getFullYear();
  const month = base.getMonth();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const firstWeekday = (new Date(year, month, 1).getDay() + 6) % 7;
  const itemsByDate = buildCalendarItems(instructions, managedTasks, year, month);
  const todayKey = dateKey(now);

  const cells: (number | null)[] = [
    ...Array.from({ length: firstWeekday }, () => null),
    ...Array.from({ length: daysInMonth }, (_, index) => index + 1),
  ];

  const startEdit = (item: CalendarItem) => {
    if (viewer) return;
    setEditing(item);
    setDraft({
      due_at: item.due_at || "",
      due_time: item.due_time || "",
      content: item.snippet,
      status: item.status && item.status !== "已错过" ? item.status : "待安排",
    });
    setEditError("");
  };

  const saveTodo = async () => {
    if (!editing?.id || !draft) return;
    setBusy(true);
    try {
      await api.updateExecutionTodo(editing.id, draft);
      setEditing(null);
      setDraft(null);
      onRefresh();
    } catch (err) {
      setEditError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const dispatchTodo = async (id?: string) => {
    if (!id) return;
    setBusy(true);
    try {
      await api.dispatchExecutionTodo(id);
      onRefresh();
    } catch (err) {
      setEditError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const runScheduler = async () => {
    setBusy(true);
    try {
      await api.runPlanScheduler();
      onRefresh();
    } catch (err) {
      setEditError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const rebuildTodos = async () => {
    setBusy(true);
    try {
      for (const item of instructions) {
        if (item.tasks.some((task) => task.todo)) {
          await api.rebuildInstructionPlan(item.id);
        }
      }
      onRefresh();
    } catch (err) {
      setEditError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>
          <CalendarDays size={16} /> 内容排期
        </h2>
        <div className="calendar-tools">
          <WriteGate>
            <button type="button" className="btn small" disabled={busy} onClick={runScheduler}>
              立即检查下发
            </button>
            <button type="button" className="btn small" disabled={busy} onClick={rebuildTodos}>
              重算待办
            </button>
          </WriteGate>
          <div className="calendar-nav">
            <button type="button" className="btn small" onClick={() => setMonthOffset(monthOffset - 1)}>
              <ChevronLeft size={14} />
            </button>
            <span className="calendar-title">{year} 年 {month + 1} 月</span>
            <button type="button" className="btn small" onClick={() => setMonthOffset(monthOffset + 1)}>
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </div>
      <div className="calendar-legend">
        <span className="cal-legend task">执行任务</span>
        <span className="cal-legend plan">可编辑待办</span>
      </div>
      {editError && !editing && <p className="error-text">{editError}</p>}
      {editing && draft && (
        <div className="todo-editor">
          <div className="todo-editor-head">
            <span>编辑待办 · {editing.channel}</span>
            <span className="cell-muted">保存后日历自动刷新，未发送项将按新时间自动下发</span>
          </div>
          <div className="todo-editor-grid">
            <label className="field">
              <span>日期</span>
              <input
                type="date"
                value={draft.due_at}
                onChange={(event) => setDraft({ ...draft, due_at: event.target.value })}
              />
            </label>
            <label className="field">
              <span>时间</span>
              <input
                type="time"
                value={draft.due_time}
                onChange={(event) => setDraft({ ...draft, due_time: event.target.value })}
              />
            </label>
            <label className="field">
              <span>状态</span>
              <select value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value })}>
                <option value="待安排">待安排</option>
                <option value="已暂停">已暂停</option>
                <option value="已跳过">已跳过</option>
              </select>
            </label>
          </div>
          <textarea
            className="todo-content"
            value={draft.content}
            onChange={(event) => setDraft({ ...draft, content: event.target.value })}
          />
          {editError && <p className="error-text">{editError}</p>}
          <div className="todo-editor-actions">
            <button type="button" className="btn small" disabled={busy} onClick={saveTodo}>
              保存
            </button>
            <button type="button" className="btn small" onClick={() => setEditing(null)}>
              取消
            </button>
          </div>
        </div>
      )}
      <div className="calendar-grid">
        {WEEKDAYS.map((weekday) => (
          <div key={weekday} className="cal-head">
            {weekday}
          </div>
        ))}
        {cells.map((day, index) => {
          if (day === null) {
            return <div key={`empty-${index}`} className="cal-cell empty" />;
          }
          const key = `${year}-${pad2(month + 1)}-${pad2(day)}`;
          const items = itemsByDate[key] || [];
          return (
            <div key={key} className={`cal-cell ${key === todayKey ? "today" : ""}`}>
              <div className="cal-day">{day}</div>
              {items.slice(0, 4).map((item, itemIndex) => {
                const terminal =
                  item.status === "已完成" ||
                  item.status === "已拦截" ||
                  item.status === "已失败";
                return (
                  <div key={`${key}-${itemIndex}`} className={`cal-item ${item.kind}`} title={item.snippet}>
                    <button type="button" className="cal-edit" onClick={() => item.todo && startEdit(item)}>
                      <span className="cal-channel">{item.channel}</span>
                      <span className="cal-label">
                        {item.label}
                        {item.time ? ` ${item.time}` : ""}
                        {item.status ? ` · ${item.status}` : ""}
                      </span>
                    </button>
                    {item.todo && !terminal && !viewer && (
                      <button type="button" className="cal-send" disabled={busy} onClick={() => dispatchTodo(item.id)}>
                        {item.status === "已错过" ? "补发" : "立即下发"}
                      </button>
                    )}
                  </div>
                );
              })}
              {items.length > 4 && <div className="cal-more">+{items.length - 4} 项</div>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
