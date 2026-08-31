import { useEffect, useState } from "react";
import { api } from "../api";

type RunLog = {
  id: string;
  instruction_id: string | null;
  module: string;
  event: string;
  detail: string | null;
  operator: string;
  extra: Record<string, unknown> | null;
  created_at: string | null;
};

const MODULE_LABELS: Record<string, string> = {
  instruction: "指令",
  execution: "执行",
  flywheel: "飞轮",
  feishu: "飞书",
  guardrail: "护栏",
};

const EVENT_COLORS: Record<string, string> = {
  created: "#3b82f6",
  generated: "#f59e0b",
  revised: "#8b5cf6",
  approved: "#16a34a",
  rejected: "#ef4444",
  dispatched: "#06b6d4",
  feedback_collected: "#6366f1",
};

export default function RunLog() {
  const [logs, setLogs] = useState<RunLog[]>([]);
  const [filterModule, setFilterModule] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    api
      .listRunlogs(filterModule ? { module: filterModule, limit: 200 } : { limit: 200 })
      .then((rows) => setLogs(rows))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [filterModule]);

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>运行日志</h1>
          <p>系统全链路运行存档，记录指令、策略、执行、飞书等关键事件</p>
        </div>
        {error && <span className="error-text">{error}</span>}
      </header>

      <div className="sub-tabs">
        <button
          type="button"
          className={`sub-tab ${!filterModule ? "active" : ""}`}
          onClick={() => setFilterModule("")}
        >
          全部
        </button>
        {Object.entries(MODULE_LABELS).map(([key, label]) => (
          <button
            type="button"
            key={key}
            className={`sub-tab ${filterModule === key ? "active" : ""}`}
            onClick={() => setFilterModule(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="empty">加载中...</div>
      ) : logs.length === 0 ? (
        <div className="empty">暂无运行日志</div>
      ) : (
        <div className="timeline">
          {logs.map((log) => {
            const color = EVENT_COLORS[log.event] || "#6b7280";
            return (
              <div key={log.id} className="timeline-item">
                <div className="timeline-dot" style={{ background: color }} />
                <div className="timeline-content">
                  <div className="timeline-head">
                    <span className="tag" style={{ background: `${color}18`, color }}>
                      {MODULE_LABELS[log.module] || log.module} · {log.event}
                    </span>
                    <span className="cell-muted" style={{ fontSize: 12 }}>
                      {log.created_at ? new Date(log.created_at).toLocaleString("zh-CN") : "-"}
                    </span>
                    <span className="cell-muted" style={{ fontSize: 12 }}>
                      操作人：{log.operator}
                    </span>
                  </div>
                  {log.detail && <p className="cell-text">{log.detail}</p>}
                  {log.instruction_id && (
                    <span className="cell-muted" style={{ fontSize: 11 }}>
                      指令ID：{log.instruction_id.slice(0, 8)}...
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
