import { Cpu } from "lucide-react";
import { Pencil, Trash2, Settings } from "lucide-react";
import { useEffect, useState } from "react";

import { WriteGate } from "../components/WriteGate";

import { api } from "../api";
import type { LLMModel, LLMUsage } from "../types";

interface ModelForm {
  name: string;
  provider: string;
  model: string;
  base_url: string;
  api_key: string;
  priority: number;
  complexity: string;
  cost_per_million: number;
  enabled: boolean;
}

export default function Models() {
  const [models, setModels] = useState<LLMModel[]>([]);
  const [usage, setUsage] = useState<LLMUsage | null>(null);
  const [error, setError] = useState("");
  const [presets, setPresets] = useState<Record<string, string>[]>([]);
  const [modal, setModal] = useState<null | {
    mode: "add-preset" | "add-custom" | "edit";
    preset?: Record<string, string>;
    model?: LLMModel;
  }>(null);
  const [form, setForm] = useState<ModelForm>({
    name: "", provider: "", model: "", base_url: "",
    api_key: "", priority: 1, complexity: "complex",
    cost_per_million: 0, enabled: true,
  });
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

  const openAddPreset = (preset: Record<string, string>) => {
    setForm({
      name: preset.name, provider: preset.provider, model: preset.model,
      base_url: preset.base_url, api_key: "",
      priority: models.length + 1, complexity: preset.complexity,
      cost_per_million: parseFloat(preset.cost_per_million) || 0, enabled: true,
    });
    setModal({ mode: "add-preset", preset });
  };

  const openAddCustom = () => {
    setForm({
      name: "", provider: "", model: "", base_url: "",
      api_key: "", priority: models.length + 1,
      complexity: "complex", cost_per_million: 0, enabled: true,
    });
    setModal({ mode: "add-custom" });
  };

  const openEdit = (model: LLMModel) => {
    setForm({
      name: model.name, provider: model.provider, model: model.model,
      base_url: model.base_url, api_key: "",
      priority: model.priority, complexity: model.complexity,
      cost_per_million: model.cost_per_million, enabled: model.enabled,
    });
    setModal({ mode: "edit", model });
  };

  const save = async () => {
    if (!modal) return;
    setSaving(true);
    setNotice("");
    try {
      const payload = {
        name: form.name, provider: form.provider, model: form.model,
        base_url: form.base_url, api_key: form.api_key || undefined,
        priority: form.priority, complexity: form.complexity,
        cost_per_million: form.cost_per_million, enabled: form.enabled,
      };
      if (modal.mode === "edit" && modal.model) {
        await api.llmUpdateModel(modal.model.id, payload);
        setNotice("模型更新成功");
      } else {
        await api.llmCreateModel(payload);
        setNotice("模型添加成功");
      }
      setModal(null);
      reloadModels();
    } catch (e) {
      setError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setSaving(false);
    }
  };

  const del = async (model: LLMModel) => {
    if (!confirm(`确定删除「${model.name}」吗？`)) return;
    try {
      await api.llmDeleteModel(model.id);
      setNotice("模型已删除");
      reloadModels();
    } catch (e) {
      setError(e instanceof Error ? e.message : "删除失败");
    }
  };

  const toggleEnabled = async (model: LLMModel) => {
    try {
      await api.llmUpdateModel(model.id, {
        name: model.name, provider: model.provider, model: model.model,
        base_url: model.base_url, priority: model.priority,
        complexity: model.complexity, cost_per_million: model.cost_per_million,
        enabled: !model.enabled,
      });
      reloadModels();
    } catch (e) {
      setError(e instanceof Error ? e.message : "切换失败");
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
          <WriteGate>
            <button type="button" className="btn small" onClick={openAddCustom}>
              <Settings size={14} style={{ verticalAlign: "middle", marginRight: 4 }} />
              自定义模型
            </button>
          </WriteGate>
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
                <button type="button" className="btn small primary" style={{ marginTop: 8 }} onClick={() => openAddPreset(preset)}>
                  添加此模型
                </button>
              </WriteGate>
            </div>
          ))}
        </div>
      </section>

      {modal && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h3>
                {modal.mode === "edit"
                  ? `编辑模型：${modal.model?.name}`
                  : `添加模型：${modal.preset?.name ?? (form.name || "自定义")}`}
              </h3>
            </div>
            <div className="modal-body">
              {(modal.mode === "add-custom" || modal.mode === "edit") && (
                <>
                  <label className="form-label">名称</label>
                  <input className="form-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="模型名称" />
                  {modal.mode === "add-custom" && (
                    <>
                      <label className="form-label" style={{ marginTop: 12 }}>Provider</label>
                      <select className="form-input" value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })}>
                        <option value="">选择 Provider</option>
                        <option value="deepseek">deepseek</option>
                        <option value="openai">openai</option>
                        <option value="zhipu">zhipu</option>
                        <option value="qwen">qwen</option>
                        <option value="ytx">ytx</option>
                        <option value="ollama">ollama</option>
                        <option value="hunyuan">hunyuan</option>
                      </select>
                      <label className="form-label" style={{ marginTop: 12 }}>Model ID</label>
                      <input className="form-input" value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} placeholder="如 deepseek-v4-pro-0813" />
                    </>
                  )}
                  {modal.mode === "edit" && (
                    <>
                      <label className="form-label" style={{ marginTop: 12 }}>Base URL</label>
                      <input className="form-input" value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} />
                      <label className="form-label" style={{ marginTop: 12 }}>Model ID</label>
                      <input className="form-input" value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} />
                      <div className="tag-row" style={{ marginTop: 8 }}>
                        <span className="cell-muted">Provider: {form.provider}</span>
                      </div>
                    </>
                  )}
                  {modal.mode === "add-custom" && (
                    <>
                      <label className="form-label" style={{ marginTop: 12 }}>Base URL</label>
                      <input className="form-input" value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} placeholder="OpenAI 兼容格式的 API 地址" />
                    </>
                  )}
                </>
              )}
              <label className="form-label" style={{ marginTop: 12 }}>API Key</label>
              <input
                type="password"
                className="form-input"
                placeholder={
                  modal.mode === "edit"
                    ? "留空则不修改已有 Key"
                    : form.provider === "ollama" ? "本地模型无需 Key，可留空" : "输入 API Key"
                }
                value={form.api_key}
                onChange={(e) => setForm({ ...form, api_key: e.target.value })}
              />
              <label className="form-label" style={{ marginTop: 12 }}>复杂度</label>
              <select className="form-input" value={form.complexity} onChange={(e) => setForm({ ...form, complexity: e.target.value })}>
                <option value="complex">complex（复杂任务）</option>
                <option value="lite">lite（轻量任务）</option>
                <option value="simple">simple（简单任务）</option>
                <option value="embedding">embedding（向量）</option>
              </select>
              <div style={{ display: "flex", gap: 16, marginTop: 12 }}>
                <div style={{ flex: 1 }}>
                  <label className="form-label">优先级（越小越优先）</label>
                  <input type="number" className="form-input" value={form.priority} onChange={(e) => setForm({ ...form, priority: parseInt(e.target.value) || 1 })} />
                </div>
                <div style={{ flex: 1 }}>
                  <label className="form-label">成本/百万 Token</label>
                  <input type="number" step="0.1" className="form-input" value={form.cost_per_million} onChange={(e) => setForm({ ...form, cost_per_million: parseFloat(e.target.value) || 0 })} />
                </div>
              </div>
              {modal.mode === "edit" && (
                <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12 }}>
                  <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
                  <span>启用</span>
                </label>
              )}
              {modal.mode === "add-preset" && (
                <p className="cell-muted" style={{ marginTop: 8 }}>
                  Provider: {form.provider} · Model: {form.model} · URL: {form.base_url}
                </p>
              )}
            </div>
            <div className="modal-foot">
              <button type="button" className="btn" onClick={() => setModal(null)}>取消</button>
              <WriteGate>
                <button type="button" className="btn primary" onClick={save} disabled={saving}>
                  {saving ? "保存中..." : "保存"}
                </button>
              </WriteGate>
            </div>
          </div>
        </div>
      )}

      <section className="panel">
        <div className="panel-head">
          <h2>模型配置（当前品牌）</h2>
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
                <th>成本/百万Token</th>
                <th>Key</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {models.map((model) => (
                <tr key={model.id}>
                  <td className="cell-main">{model.name}</td>
                  <td>{model.provider}</td>
                  <td>{model.model}</td>
                  <td><span className={`pill ${model.complexity}`}>{model.complexity}</span></td>
                  <td>{model.priority}</td>
                  <td>¥{model.cost_per_million}</td>
                  <td>{model.has_key ? "已配置" : "未配置"}</td>
                  <td>
                    <button
                      type="button"
                      className={`pill ${model.enabled ? "enabled" : "disabled"}`}
                      style={{ cursor: "pointer", border: "none", background: "none" }}
                      onClick={() => toggleEnabled(model)}
                    >
                      {model.enabled ? "启用" : "停用"}
                    </button>
                  </td>
                  <td>
                    <WriteGate>
                      <button type="button" className="btn small" style={{ marginRight: 4 }} onClick={() => openEdit(model)}>
                        <Pencil size={12} style={{ verticalAlign: "middle" }} />
                      </button>
                      <button type="button" className="btn small" onClick={() => del(model)}>
                        <Trash2 size={12} style={{ verticalAlign: "middle" }} />
                      </button>
                    </WriteGate>
                  </td>
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
                      <td>{log.prompt_tokens} + {log.completion_tokens}</td>
                      <td>{log.latency_ms} ms</td>
                      <td>¥{log.cost}</td>
                      <td><span className={`pill ${log.status}`}>{log.status}</span></td>
                      <td className="cell-muted">{log.created_at ? new Date(log.created_at).toLocaleString() : "-"}</td>
                    </tr>
                  ))}
                  {usage.logs.length === 0 && (
                    <tr><td colSpan={6} className="empty">暂无调用记录</td></tr>
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
