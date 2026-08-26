import { Cpu } from "lucide-react";
import { Plus } from "lucide-react";
import { useEffect, useState } from "react";

import { WriteGate } from "../components/WriteGate";

import { api } from "../api";
import type { LLMModel, LLMUsage } from "../types";

export default function Models() {
  const [models, setModels] = useState<LLMModel[]>([]);
  const [usage, setUsage] = useState<LLMUsage | null>(null);
  const [error, setError] = useState("");
  const [presets, setPresets] = useState<Record<string, string>[]>([]);
  const [addPreset, setAddPreset] = useState<Record<string, string> | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    Promise.all([api.llmModels(), api.llmUsage(), api.llmPresets()])
      .then(([modelRows, usageRows, presetRows]) => {
        setModels(modelRows);
        setUsage(usageRows);
        setPresets(presetRows as Record<string, string>[]);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  const reloadModels = () => {
    api.llmModels().then(setModels).catch((err: Error) => setError(err.message));
  };

  const savePreset = async () => {
    if (!addPreset) return;
    setSaving(true);
    setNotice("");
    try {
      await api.llmCreateModel({
        name: addPreset.name,
        provider: addPreset.provider,
        model: addPreset.model,
        base_url: addPreset.base_url,
        api_key: apiKey,
        complexity: addPreset.complexity,
        cost_per_million: parseFloat(addPreset.cost_per_million) || 0,
        priority: models.length + 1,
      });
      setAddPreset(null);
      setApiKey("");
      setNotice("模型添加成功");
      reloadModels();
    } catch (e) {
      setError(e instanceof Error ? e.message : "添加失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>LLM 网关</h1>
          <p>多模型路由、降级与 Token 预算</p>
        </div>
        {error && <span className="error-text">{error}</span>}
        {notice && <span className="success-text">{notice}</span>}
      </header>

      <section className="panel">
        <div className="panel-head">
          <h2>快速配置</h2>
          <Plus size={16} className="panel-icon" />
        </div>
        <div className="preset-grid">
          {presets.map((preset, i) => (
            <div key={i} className="preset-card">
              <span className="cell-main">{preset.name}</span>
              <p className="cell-muted">{preset.description}</p>
              <div className="tag-row" style={{ marginTop: 6 }}>
                <span className={`pill ${preset.complexity}`}>{preset.complexity}</span>
                {parseFloat(preset.cost_per_million) === 0 ? (
                  <span className="tag">免费</span>
                ) : (
                  <span className="tag">¥{preset.cost_per_million}/百万</span>
                )}
              </div>
              <WriteGate>
                <button type="button" className="btn small primary" style={{ marginTop: 8 }} onClick={() => { setAddPreset(preset); setApiKey(""); }}>
                  添加此模型
                </button>
              </WriteGate>
            </div>
          ))}
        </div>
      </section>

      {addPreset && (
        <div className="modal-overlay" onClick={() => setAddPreset(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h3>添加模型：{addPreset.name}</h3>
            </div>
            <div className="modal-body">
              <label className="form-label">API Key</label>
              <input
                type="password"
                className="form-input"
                placeholder={addPreset.provider === "ollama" ? "本地模型无需 Key，可留空" : "输入 API Key"}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />
              <p className="cell-muted" style={{ marginTop: 8 }}>
                Provider: {addPreset.provider} · Model: {addPreset.model} · URL: {addPreset.base_url}
              </p>
            </div>
            <div className="modal-foot">
              <button type="button" className="btn" onClick={() => setAddPreset(null)}>取消</button>
              <WriteGate>
                <button type="button" className="btn primary" onClick={savePreset} disabled={saving}>
                  {saving ? "保存中..." : "保存"}
                </button>
              </WriteGate>
            </div>
          </div>
        </div>
      )}

      <section className="panel">
        <div className="panel-head">
          <h2>模型配置</h2>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>名称</th>
                <th>Provider</th>
                <th>模型</th>
                <th>复杂度</th>
                <th>优先级</th>
                <th>成本/百万 Token</th>
                <th>Key</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {models.map((model) => (
                <tr key={model.id}>
                  <td className="cell-main">{model.name}</td>
                  <td>{model.provider}</td>
                  <td>{model.model}</td>
                  <td>
                    <span className={`pill ${model.complexity}`}>{model.complexity}</span>
                  </td>
                  <td>{model.priority}</td>
                  <td>¥{model.cost_per_million}</td>
                  <td>{model.has_key ? "已配置" : "未配置"}</td>
                  <td>{model.enabled ? "启用" : "停用"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>预算与用量</h2>
          <Cpu size={16} className="panel-icon" />
        </div>
        {usage && (
          <>
            <div className="metric-row">
              {usage.budgets.slice(0, 4).map((budget) => (
                <div key={budget.id} className="metric">
                  <span className="metric-label">
                    {budget.period_type} · {budget.period_key}
                  </span>
                  <span className="metric-value">
                    {budget.tokens_used.toLocaleString()} / {budget.token_limit.toLocaleString()}
                  </span>
                  <span className="cell-muted">成本 ¥{budget.cost_used}</span>
                </div>
              ))}
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>模型</th>
                    <th>Token</th>
                    <th>延迟</th>
                    <th>成本</th>
                    <th>状态</th>
                    <th>时间</th>
                  </tr>
                </thead>
                <tbody>
                  {usage.logs.map((log) => (
                    <tr key={log.id}>
                      <td className="cell-main">{log.model}</td>
                      <td>
                        {log.prompt_tokens} + {log.completion_tokens}
                      </td>
                      <td>{log.latency_ms} ms</td>
                      <td>¥{log.cost}</td>
                      <td>
                        <span className={`pill ${log.status}`}>{log.status}</span>
                      </td>
                      <td className="cell-muted">
                        {log.created_at ? new Date(log.created_at).toLocaleString() : "-"}
                      </td>
                    </tr>
                  ))}
                  {usage.logs.length === 0 && (
                    <tr>
                      <td colSpan={6} className="empty">
                        暂无调用记录
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
