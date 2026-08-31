import { useEffect, useState } from "react";

import { api } from "../api";
import type { GuardrailHit, GuardrailRule } from "../types";

export default function Guardrails() {
  const [hits, setHits] = useState<GuardrailHit[]>([]);
  const [rules, setRules] = useState<GuardrailRule[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.guardrailHits(), api.guardrailRules()])
      .then(([hitRows, ruleRows]) => {
        setHits(hitRows);
        setRules(ruleRows);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>护栏中心</h1>
          <p>敏感词拦截、内容审核与转人工兜底</p>
        </div>
        {error && <span className="error-text">{error}</span>}
      </header>

      <section className="panel">
        <div className="panel-head">
          <h2>规则</h2>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>名称</th>
                <th>类型</th>
                <th>动作</th>
                <th>关键词</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={rule.id}>
                  <td className="cell-main">{rule.name}</td>
                  <td>{rule.rule_type}</td>
                  <td>
                    <span className={`pill ${rule.action}`}>{rule.action}</span>
                  </td>
                  <td className="cell-muted">{rule.pattern.join("、")}</td>
                  <td>{rule.enabled ? "启用" : "停用"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>命中记录</h2>
        </div>
        <div className="hit-list">
          {hits.map((hit) => (
            <div key={hit.id} className="hit-item">
              <div className="hit-head">
                <span className={`pill ${hit.action}`}>{hit.action}</span>
                <span className="cell-muted">
                  {hit.created_at ? new Date(hit.created_at).toLocaleString() : "-"}
                </span>
              </div>
              <p>{hit.content}</p>
              {hit.note && <div className="hit-note">{hit.note}</div>}
            </div>
          ))}
          {hits.length === 0 && <div className="empty">暂无命中记录</div>}
        </div>
      </section>
    </div>
  );
}

