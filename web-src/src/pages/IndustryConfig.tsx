import { Plus, Save, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { api } from "../api";
import { WriteGate } from "../components/WriteGate";
import type {
  IndustryRow,
  IndustryTemplateRow,
  ProductItem,
  Workbench,
} from "../types";

const KIND_LABELS: Record<string, string> = {
  activity: "活动配置",
  catalog: "货盘配置",
  sales: "销售配置",
  content: "内容配置",
  kpi: "KPI 与标签",
};

const LIST_KEYS: Record<string, string[]> = {
  activity: ["types"],
  catalog: ["structure", "fields"],
  sales: ["sections", "layers"],
  content: ["channels", "fields"],
  kpi: ["metrics"],
};

const KEY_LABELS: Record<string, string> = {
  types: "活动类型",
  structure: "货盘结构",
  fields: "字段",
  sections: "执行模块",
  layers: "客户分层",
  channels: "渠道",
  metrics: "指标",
};

export type TabKey = "overview" | "catalog" | "activity" | "sales" | "content" | "kpi";

const TABS: { key: TabKey; label: string }[] = [
  { key: "overview", label: "行业概览" },
  { key: "catalog", label: "货盘配置" },
  { key: "activity", label: "活动配置" },
  { key: "sales", label: "销售配置" },
  { key: "content", label: "内容配置" },
  { key: "kpi", label: "KPI 与标签" },
];

interface ObjectionRow {
  issue: string;
  response: string;
  tone: string;
  scenario: string;
}

interface LayerPlayRow {
  layer: string;
  goal: string;
  action: string;
  script: string;
  follow_up: string;
}

interface MaterialRow {
  type: string;
  title: string;
  copy: string;
  channel: string;
  purpose: string;
}

interface ScheduleRow {
  channel: string;
  cadence: string;
  time_slots: string;
  content_type: string;
  goal: string;
}

function ListEditor({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string[];
  onChange: (next: string[]) => void;
}) {
  const [draft, setDraft] = useState("");

  const add = () => {
    if (!draft.trim()) return;
    onChange([...value, draft.trim()]);
    setDraft("");
  };

  return (
    <div className="template-editor">
      <div className="template-editor-label">{label}</div>
      <div className="tag-row">
        {value.map((item) => (
          <span key={item} className="tag">
            {item}
            <button
              type="button"
              className="tag-remove"
              aria-label={`删除${item}`}
              onClick={() => onChange(value.filter((v) => v !== item))}
            >
              <X size={12} />
            </button>
          </span>
        ))}
      </div>
      <div className="simulate-bar">
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && add()}
          placeholder={`添加${label}`}
        />
        <button type="button" className="btn small" onClick={add}>
          <Plus size={14} />
          添加
        </button>
      </div>
    </div>
  );
}

function TemplatePanel({
  template,
  onSave,
  onUpdate,
}: {
  template: IndustryTemplateRow;
  onSave: (template: IndustryTemplateRow) => void;
  onUpdate: (templateId: string, key: string, next: string[]) => void;
}) {
  const data = (template.data as Record<string, unknown>) ?? {};
  const keys = LIST_KEYS[template.kind] ?? [];
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{KIND_LABELS[template.kind] || template.kind}</h2>
        <WriteGate>
          <button type="button" className="btn primary small" onClick={() => onSave(template)}>
            <Save size={14} />
            保存
          </button>
        </WriteGate>
      </div>
      {keys.map((key) => (
        <ListEditor
          key={key}
          label={KEY_LABELS[key] || key}
          value={Array.isArray(data[key]) ? (data[key] as string[]) : []}
          onChange={(next) => onUpdate(template.id, key, next)}
        />
      ))}
    </section>
  );
}

function SalesPanel({
  template,
  onSave,
  onUpdate,
  onUpdateRows,
}: {
  template: IndustryTemplateRow;
  onSave: (template: IndustryTemplateRow) => void;
  onUpdate: (templateId: string, key: string, next: string[]) => void;
  onUpdateRows: (templateId: string, key: string, rows: unknown[]) => void;
}) {
  const data = (template.data as Record<string, unknown>) ?? {};
  const sections = Array.isArray(data.sections) ? (data.sections as string[]) : [];
  const objections = Array.isArray(data.objections) ? (data.objections as ObjectionRow[]) : [];
  const layerPlays = Array.isArray(data.layer_plays) ? (data.layer_plays as LayerPlayRow[]) : [];
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>销售配置</h2>
        <WriteGate>
          <button type="button" className="btn primary small" onClick={() => onSave(template)}>
            <Save size={14} />
            保存
          </button>
        </WriteGate>
      </div>
      <ListEditor
        label="执行模块"
        value={sections}
        onChange={(next) => onUpdate(template.id, "sections", next)}
      />
      <ObjectionEditor
        value={objections}
        onChange={(rows) => onUpdateRows(template.id, "objections", rows)}
      />
      <LayerPlayEditor
        value={layerPlays}
        onChange={(rows) => onUpdateRows(template.id, "layer_plays", rows)}
      />
    </section>
  );
}

function ContentPanel({
  template,
  onSave,
  onUpdate,
  onUpdateRows,
}: {
  template: IndustryTemplateRow;
  onSave: (template: IndustryTemplateRow) => void;
  onUpdate: (templateId: string, key: string, next: string[]) => void;
  onUpdateRows: (templateId: string, key: string, rows: unknown[]) => void;
}) {
  const data = (template.data as Record<string, unknown>) ?? {};
  const channels = Array.isArray(data.channels) ? (data.channels as string[]) : [];
  const materials = Array.isArray(data.materials) ? (data.materials as MaterialRow[]) : [];
  const schedules = Array.isArray(data.schedules) ? (data.schedules as ScheduleRow[]) : [];
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>内容配置</h2>
        <WriteGate>
          <button type="button" className="btn primary small" onClick={() => onSave(template)}>
            <Save size={14} />
            保存
          </button>
        </WriteGate>
      </div>
      <ListEditor
        label="渠道"
        value={channels}
        onChange={(next) => onUpdate(template.id, "channels", next)}
      />
      <MaterialEditor
        value={materials}
        onChange={(rows) => onUpdateRows(template.id, "materials", rows)}
      />
      <ScheduleEditor
        value={schedules}
        onChange={(rows) => onUpdateRows(template.id, "schedules", rows)}
      />
    </section>
  );
}

function ObjectionEditor({
  value,
  onChange,
}: {
  value: ObjectionRow[];
  onChange: (next: ObjectionRow[]) => void;
}) {
  const add = () => {
    onChange([...value, { issue: "", response: "", tone: "", scenario: "" }]);
  };
  const update = (index: number, field: keyof ObjectionRow, next: string) => {
    onChange(value.map((row, i) => (i === index ? { ...row, [field]: next } : row)));
  };
  return (
    <div className="template-editor">
      <div className="template-editor-label">异议处理库</div>
      {value.map((row, index) => (
        <div key={index} className="structured-row">
          <input value={row.issue} onChange={(event) => update(index, "issue", event.target.value)} placeholder="常见异议" />
          <input value={row.tone} onChange={(event) => update(index, "tone", event.target.value)} placeholder="语气" />
          <input value={row.scenario} onChange={(event) => update(index, "scenario", event.target.value)} placeholder="适用场景" />
          <textarea value={row.response} onChange={(event) => update(index, "response", event.target.value)} placeholder="应对话术" rows={2} />
          <button type="button" className="icon-btn ghost" onClick={() => onChange(value.filter((_, i) => i !== index))} aria-label="删除">
            <Trash2 size={14} />
          </button>
        </div>
      ))}
      <button type="button" className="btn small" onClick={add}>
        <Plus size={14} />
        添加异议
      </button>
    </div>
  );
}

function LayerPlayEditor({
  value,
  onChange,
}: {
  value: LayerPlayRow[];
  onChange: (next: LayerPlayRow[]) => void;
}) {
  const add = () => {
    onChange([...value, { layer: "", goal: "", action: "", script: "", follow_up: "" }]);
  };
  const update = (index: number, field: keyof LayerPlayRow, next: string) => {
    onChange(value.map((row, i) => (i === index ? { ...row, [field]: next } : row)));
  };
  return (
    <div className="template-editor">
      <div className="template-editor-label">分层打法</div>
      {value.map((row, index) => (
        <div key={index} className="structured-row">
          <input value={row.layer} onChange={(event) => update(index, "layer", event.target.value)} placeholder="客户分层" />
          <input value={row.goal} onChange={(event) => update(index, "goal", event.target.value)} placeholder="核心目标" />
          <input value={row.action} onChange={(event) => update(index, "action", event.target.value)} placeholder="关键动作" />
          <input value={row.follow_up} onChange={(event) => update(index, "follow_up", event.target.value)} placeholder="跟进节奏" />
          <textarea value={row.script} onChange={(event) => update(index, "script", event.target.value)} placeholder="话术要点" rows={2} />
          <button type="button" className="icon-btn ghost" onClick={() => onChange(value.filter((_, i) => i !== index))} aria-label="删除">
            <Trash2 size={14} />
          </button>
        </div>
      ))}
      <button type="button" className="btn small" onClick={add}>
        <Plus size={14} />
        添加分层打法
      </button>
    </div>
  );
}

function MaterialEditor({
  value,
  onChange,
}: {
  value: MaterialRow[];
  onChange: (next: MaterialRow[]) => void;
}) {
  const add = () => {
    onChange([...value, { type: "", title: "", copy: "", channel: "", purpose: "" }]);
  };
  const update = (index: number, field: keyof MaterialRow, next: string) => {
    onChange(value.map((row, i) => (i === index ? { ...row, [field]: next } : row)));
  };
  return (
    <div className="template-editor">
      <div className="template-editor-label">素材库</div>
      {value.map((row, index) => (
        <div key={index} className="structured-row">
          <input value={row.type} onChange={(event) => update(index, "type", event.target.value)} placeholder="素材类型" />
          <input value={row.title} onChange={(event) => update(index, "title", event.target.value)} placeholder="标题" />
          <input value={row.channel} onChange={(event) => update(index, "channel", event.target.value)} placeholder="适用渠道" />
          <input value={row.purpose} onChange={(event) => update(index, "purpose", event.target.value)} placeholder="发布用途" />
          <textarea value={row.copy} onChange={(event) => update(index, "copy", event.target.value)} placeholder="文案" rows={2} />
          <button type="button" className="icon-btn ghost" onClick={() => onChange(value.filter((_, i) => i !== index))} aria-label="删除">
            <Trash2 size={14} />
          </button>
        </div>
      ))}
      <button type="button" className="btn small" onClick={add}>
        <Plus size={14} />
        添加素材
      </button>
    </div>
  );
}

function ScheduleEditor({
  value,
  onChange,
}: {
  value: ScheduleRow[];
  onChange: (next: ScheduleRow[]) => void;
}) {
  const add = () => {
    onChange([...value, { channel: "", cadence: "", time_slots: "", content_type: "", goal: "" }]);
  };
  const update = (index: number, field: keyof ScheduleRow, next: string) => {
    onChange(value.map((row, i) => (i === index ? { ...row, [field]: next } : row)));
  };
  return (
    <div className="template-editor">
      <div className="template-editor-label">排期规则</div>
      {value.map((row, index) => (
        <div key={index} className="structured-row">
          <input value={row.channel} onChange={(event) => update(index, "channel", event.target.value)} placeholder="渠道" />
          <input value={row.cadence} onChange={(event) => update(index, "cadence", event.target.value)} placeholder="频次" />
          <input value={row.time_slots} onChange={(event) => update(index, "time_slots", event.target.value)} placeholder="发布时间" />
          <input value={row.goal} onChange={(event) => update(index, "goal", event.target.value)} placeholder="目标" />
          <textarea value={row.content_type} onChange={(event) => update(index, "content_type", event.target.value)} placeholder="内容类型" rows={1} />
          <button type="button" className="icon-btn ghost" onClick={() => onChange(value.filter((_, i) => i !== index))} aria-label="删除">
            <Trash2 size={14} />
          </button>
        </div>
      ))}
      <button type="button" className="btn small" onClick={add}>
        <Plus size={14} />
        添加排期
      </button>
    </div>
  );
}

export default function IndustryConfig({
  embeddedTab,
  compact = false,
}: {
  embeddedTab?: TabKey;
  compact?: boolean;
}) {
  const [industries, setIndustries] = useState<IndustryRow[]>([]);
  const [industryId, setIndustryId] = useState(localStorage.getItem("pdp_industry_id") || "");
  const [tab, setTab] = useState<TabKey>("overview");
  const [templates, setTemplates] = useState<IndustryTemplateRow[]>([]);
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [workbench, setWorkbench] = useState<Workbench | null>(null);
  const [form, setForm] = useState({ name: "", category: "", price: "", efficacy: "" });
  const [importText, setImportText] = useState("");
  const [error, setError] = useState("");
  const activeTab = embeddedTab || tab;

  const currentIndustry = industries.find((item) => item.id === industryId);

  useEffect(() => {
    api
      .platformIndustries()
      .then((rows) => {
        setIndustries(rows);
        if (rows.length > 0 && !industryId) {
          const first = rows[0].id;
          localStorage.setItem("pdp_industry_id", first);
          setIndustryId(first);
        }
      })
      .catch((err: Error) => setError(err.message));
  }, [industryId]);

  const loadTemplates = useCallback((id: string) => {
    api
      .industryTemplates(id)
      .then(setTemplates)
      .catch((err: Error) => setError(err.message));
  }, []);

  const loadProducts = useCallback(() => {
    api
      .flywheelProducts()
      .then(setProducts)
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!industryId) return;
    loadTemplates(industryId);
    loadProducts();
    api
      .platformWorkbench()
      .then(setWorkbench)
      .catch((err: Error) => setError(err.message));
  }, [industryId, loadTemplates, loadProducts]);

  const updateList = (templateId: string, key: string, next: string[]) => {
    setTemplates((rows) =>
      rows.map((row) => {
        if (row.id !== templateId) return row;
        const data = { ...(row.data as Record<string, unknown>) };
        data[key] = next;
        return { ...row, data };
      }),
    );
  };

  const updateRows = (templateId: string, key: string, rows: unknown[]) => {
    setTemplates((rowsState) =>
      rowsState.map((row) => {
        if (row.id !== templateId) return row;
        const data = { ...(row.data as Record<string, unknown>) };
        data[key] = rows;
        return { ...row, data };
      }),
    );
  };

  const saveTemplate = async (template: IndustryTemplateRow) => {
    await api.updateIndustryTemplate(template.id, (template.data as Record<string, unknown>) ?? {});
  };

  const addProduct = async () => {
    if (!form.name.trim()) return;
    await api.createProduct({
      name: form.name,
      category: form.category || null,
      price: Number(form.price) || 0,
      efficacy: form.efficacy.split(/[、,，]/).map((item) => item.trim()).filter(Boolean),
      segments: [],
      seasons: [],
      is_focus: false,
    });
    setForm({ name: "", category: "", price: "", efficacy: "" });
    loadProducts();
  };

  const removeProduct = async (id: string) => {
    await api.deleteProduct(id);
    loadProducts();
  };

  const importProducts = async () => {
    const items = importText
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const parts = line.split(",");
        return {
          name: parts[0]?.trim() || "",
          category: parts[1]?.trim() || null,
          price: Number(parts[2]) || 0,
          efficacy: (parts[3] || "").split(/[、|]/).map((item) => item.trim()).filter(Boolean),
          segments: [],
          seasons: [],
          is_focus: false,
        };
      })
      .filter((item) => item.name);
    if (items.length === 0) return;
    await api.importProducts(items);
    setImportText("");
    loadProducts();
  };

  if (compact) {
    return (
      <div className="module-template">
        {activeTab === "catalog" && (
          <>
            <section className="panel">
              <div className="panel-head">
                <h2>新增品项</h2>
              </div>
              <div className="simulate-bar">
                <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="品项名称" />
                <input value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} placeholder="分类" />
                <input value={form.price} onChange={(event) => setForm({ ...form, price: event.target.value })} placeholder="价格" />
                <input value={form.efficacy} onChange={(event) => setForm({ ...form, efficacy: event.target.value })} placeholder="功效（、分隔）" />
                <WriteGate>
                  <button type="button" className="btn primary" onClick={addProduct}>
                    <Plus size={15} />
                    添加
                  </button>
                </WriteGate>
              </div>
              <textarea
                className="batch-input"
                value={importText}
                onChange={(event) => setImportText(event.target.value)}
                placeholder="批量导入，每行：名称,分类,价格,功效1、功效2"
                rows={3}
              />
              <WriteGate>
                <button type="button" className="btn small" onClick={importProducts}>
                  批量导入
                </button>
              </WriteGate>
            </section>
            <section className="panel">
              <div className="panel-head">
                <h2>货盘列表</h2>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>品项</th>
                      <th>分类</th>
                      <th>价格</th>
                      <th>功效</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {products.map((product) => (
                      <tr key={product.id}>
                        <td className="cell-main">{product.name}</td>
                        <td>{product.category || "-"}</td>
                        <td>¥{product.price}</td>
                        <td className="cell-muted">{product.efficacy.slice(0, 4).join("、") || "-"}</td>
                        <td>
                          <WriteGate>
                            <button type="button" className="icon-btn ghost" onClick={() => removeProduct(product.id)} aria-label="删除">
                              <Trash2 size={15} />
                            </button>
                          </WriteGate>
                        </td>
                      </tr>
                    ))}
                    {products.length === 0 && (
                      <tr>
                        <td colSpan={5} className="empty">
                          暂无品项
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
        {["activity", "sales", "content", "kpi"].includes(activeTab) && (
          <div className="chart-grid">
            {templates
              .filter((template) => template.kind === activeTab)
              .map((template) =>
                template.kind === "sales" ? (
                  <SalesPanel
                    key={template.id}
                    template={template}
                    onSave={saveTemplate}
                    onUpdate={updateList}
                    onUpdateRows={updateRows}
                  />
                ) : template.kind === "content" ? (
                  <ContentPanel
                    key={template.id}
                    template={template}
                    onSave={saveTemplate}
                    onUpdate={updateList}
                    onUpdateRows={updateRows}
                  />
                ) : (
                  <TemplatePanel
                    key={template.id}
                    template={template}
                    onSave={saveTemplate}
                    onUpdate={updateList}
                  />
                ),
              )}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>行业运营配置</h1>
          <p>当前行业：{currentIndustry?.name || "未选择"} · 切换行业请使用侧边栏顶部选择器</p>
        </div>
        {error && <span className="error-text">{error}</span>}
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

      {activeTab === "overview" && (
        <>
          <section className="metric-row">
            <div className="metric">
              <span className="metric-label">货盘品项</span>
              <span className="metric-value">{workbench?.counts.products ?? 0}</span>
            </div>
            <div className="metric">
              <span className="metric-label">信号</span>
              <span className="metric-value">{workbench?.counts.signals ?? 0}</span>
            </div>
            <div className="metric">
              <span className="metric-label">需求</span>
              <span className="metric-value">{workbench?.counts.demands ?? 0}</span>
            </div>
            <div className="metric">
              <span className="metric-label">策略</span>
              <span className="metric-value">{workbench?.counts.strategies ?? 0}</span>
            </div>
            <div className="metric">
              <span className="metric-label">模板</span>
              <span className="metric-value">{templates.length}/5</span>
            </div>
          </section>
          <section className="panel">
            <div className="panel-head">
              <h2>模板配置</h2>
            </div>
            <div className="tag-row">
              {templates.map((template) => (
                <span key={template.id} className="tag">
                  {KIND_LABELS[template.kind] || template.kind}
                </span>
              ))}
            </div>
          </section>
        </>
      )}

      {activeTab === "catalog" && (
        <>
          <section className="panel">
            <div className="panel-head">
              <h2>新增品项</h2>
            </div>
            <div className="simulate-bar">
              <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="品项名称" />
              <input value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} placeholder="分类" />
              <input value={form.price} onChange={(event) => setForm({ ...form, price: event.target.value })} placeholder="价格" />
              <input value={form.efficacy} onChange={(event) => setForm({ ...form, efficacy: event.target.value })} placeholder="功效（、分隔）" />
              <WriteGate>
                <button type="button" className="btn primary" onClick={addProduct}>
                  <Plus size={15} />
                  添加
                </button>
              </WriteGate>
            </div>
            <textarea
              className="batch-input"
              value={importText}
              onChange={(event) => setImportText(event.target.value)}
              placeholder="批量导入，每行：名称,分类,价格,功效1、功效2"
              rows={3}
            />
            <WriteGate>
              <button type="button" className="btn small" onClick={importProducts}>
                批量导入
              </button>
            </WriteGate>
          </section>
          <section className="panel">
            <div className="panel-head">
              <h2>货盘列表</h2>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>品项</th>
                    <th>分类</th>
                    <th>价格</th>
                    <th>功效</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {products.map((product) => (
                    <tr key={product.id}>
                      <td className="cell-main">{product.name}</td>
                      <td>{product.category || "-"}</td>
                      <td>¥{product.price}</td>
                      <td className="cell-muted">{product.efficacy.slice(0, 4).join("、") || "-"}</td>
                      <td>
                        <WriteGate>
                          <button type="button" className="icon-btn ghost" onClick={() => removeProduct(product.id)} aria-label="删除">
                            <Trash2 size={15} />
                          </button>
                        </WriteGate>
                      </td>
                    </tr>
                  ))}
                  {products.length === 0 && (
                    <tr>
                      <td colSpan={5} className="empty">
                        暂无品项
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {["activity", "sales", "content", "kpi"].includes(activeTab) && (
        <div className="chart-grid">
          {templates
            .filter((template) => template.kind === activeTab)
            .map((template) =>
              template.kind === "sales" ? (
                <SalesPanel
                  key={template.id}
                  template={template}
                  onSave={saveTemplate}
                  onUpdate={updateList}
                  onUpdateRows={updateRows}
                />
              ) : template.kind === "content" ? (
                <ContentPanel
                  key={template.id}
                  template={template}
                  onSave={saveTemplate}
                  onUpdate={updateList}
                  onUpdateRows={updateRows}
                />
              ) : (
                <TemplatePanel
                  key={template.id}
                  template={template}
                  onSave={saveTemplate}
                  onUpdate={updateList}
                />
              ),
            )}
        </div>
      )}
    </div>
  );
}
