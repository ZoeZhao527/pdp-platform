import type {
  Agent,
  AlertRow,
  ApiExampleRow,
  ApiLogRow,
  AuditLogRow,
  AuthUser,
  BrandRow,
  BrandDetail,
 BrandUserRow,
 MeteringDetail,
 CandidateRow,
  RecommendRow,
 MeteringRow,
 EffectBreakdown,
 FeedbackEventRow,
 PlatformAssetOverview,
 CampaignRow,
 ChannelCheckResult,
 Channel,
 Cockpit,
 Conversation,
 CustomerProfile,
 DataSourceRow,
 DemandProfileRow,
  DailyBriefs,
 ExecutionCenterData,
 FeishuHandleResult,
 FeishuMessageRow,
 FeishuSendResult,
 FeishuConfigRow,
 FeishuTestResult,
 FeishuSummary,
  FissionTemplateRow,
  FlywheelDashboard,
  FlywheelExecution,
  FlywheelSignal,
  FlywheelCycle,
  FlywheelAdvisories,
  FlywheelStatus,
  GuardrailHit,
  GuardrailRule,
  KnowledgeDoc,
  KnowledgeHit,
  LLMModel,
  LLMUsage,
  InfluencerRow,
  IndustryRow,
  IndustryTemplateRow,
  InstructionRow,
  MarketOverview,
  MatchItem,
  Message,
  OpsChannelRow,
  Overview,
  ProductCategory,
  ProductItem,
  ReportBlockRow,
  ReportDetail,
  ReportDocRow,
  SearchResult,
  SendPolicy,
  Strategy,
  StrategyTaskItem,
  StrategyRunResult,
  TenantRow,
  IntegrationRow,
  LoginResult,
  WebhookResult,
  Workbench,
} from "./types";

const BASE = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {};
  if (!(init?.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const tenantId = localStorage.getItem("pdp_tenant_id");
  if (tenantId) headers["X-Tenant-Id"] = tenantId;
  const industryId = localStorage.getItem("pdp_industry_id");
  if (industryId) headers["X-Industry-Id"] = industryId;
  const token = localStorage.getItem("pdp_token");
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, {
    headers,
    ...init,
  });
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = body.detail || body.message || JSON.stringify(body);
    } catch {
      detail = await res.text();
    }
    const friendly: Record<number, string> = {
      401: "登录已过期，请重新登录",
      403: "没有操作权限",
      404: "资源不存在",
      422: "参数格式不正确",
      429: "请求太频繁，请稍后重试",
      500: "服务器内部错误，请稍后重试",
      502: "网关错误，请稍后重试",
      503: "服务暂时不可用",
    };
    const msg = friendly[res.status] || detail || `请求失败 (${res.status})`;
    if (res.status === 401) {
      localStorage.removeItem("pdp_token");
      window.location.href = "/login";
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  login: (username: string, password: string) =>
    request<LoginResult>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  me: () => request<{ user: AuthUser }>("/auth/me"),
  changePassword: (oldPassword: string, newPassword: string) =>
    request<{ ok: boolean }>("/auth/password", {
      method: "POST",
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    }),
  authUsers: () => request<AuthUser[]>("/auth/users"),
  createAuthUser: (payload: { username: string; password: string; display_name?: string; role: string }) =>
    request<{ user: AuthUser }>("/auth/users", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  overview: () => request<Overview>("/admin/overview"),
  conversations: () => request<Conversation[]>("/conversations"),
  messages: (id: string) => request<Message[]>(`/conversations/${id}/messages`),
  sendMessage: (id: string, content: string) =>
    request<Message>(`/conversations/${id}/messages`, {
      method: "POST",
      body: JSON.stringify({ content, direction: "out", source: "manual" }),
    }),
  webhook: (content: string) =>
    request<WebhookResult>("/channels/mock/webhook", {
      method: "POST",
      body: JSON.stringify({ external_id: "admin-demo", content, source_type: "message" }),
    }),
  flywheelDashboard: () => request<FlywheelDashboard>("/flywheel/dashboard"),
  flywheelStatus: () => request<FlywheelStatus>("/flywheel/status"),
  flywheelAdvisories: () => request<FlywheelAdvisories>("/flywheel/advisories"),
  flywheelSignals: (limit = 50) => request<FlywheelSignal[]>(`/flywheel/signals?limit=${limit}`),
  createFlywheelSignal: (rawText: string, sourceType = "manual") =>
    request<{ id: string; status: string }>("/flywheel/signals", {
      method: "POST",
      body: JSON.stringify({ raw_text: rawText, source_type: sourceType }),
    }),
  batchFlywheelSignals: (items: string[]) =>
    request<{ added: number }>("/flywheel/signals/batch", {
      method: "POST",
      body: JSON.stringify({ items }),
    }),
  labelFlywheelSignal: (id: string) =>
    request<{ id: string; status: string; scenario: string; tags: Record<string, unknown> }>(
      `/flywheel/signals/${id}/label`,
      { method: "POST" },
    ),
  verifyDemand: (id: string) =>
    request<{ id: string; verified: boolean }>(`/flywheel/demands/${id}/verify`, { method: "POST" }),
  flywheelDemands: (limit = 50) => request<DemandProfileRow[]>(`/flywheel/demands?limit=${limit}`),
  flywheelExecutions: (limit = 50) =>
    request<FlywheelExecution[]>(`/flywheel/executions?limit=${limit}`),
  adoptCycle: (id: string) =>
    request<{ cycle_id: string; adopted: boolean }>(`/flywheel/${id}/adopt`, { method: "POST" }),
  runFlywheelAuto: (limit = 100, collectTopics = false) =>
    request<Record<string, unknown>>(
      `/flywheel/run-auto?limit=${limit}&collect_topics=${collectTopics}`,
      { method: "POST" },
    ),
  triggerFlywheel: (signalText: string) =>
    request<FlywheelCycle>("/flywheel/trigger", {
      method: "POST",
      body: JSON.stringify({ signal_text: signalText, source_type: "message" }),
    }),
  guardrailHits: () => request<GuardrailHit[]>("/admin/guardrails/hits"),
  guardrailRules: () => request<GuardrailRule[]>("/admin/guardrails/rules"),
  channels: () => request<Channel[]>("/admin/channels"),
  updateChannel: (id: string, payload: { name?: string; enabled?: boolean; config?: Record<string, unknown> }) =>
    request<Channel>(`/admin/channels/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  testChannel: (id: string) =>
    request<{ ok: boolean; message_id?: string; detail?: string }>(`/admin/channels/${id}/test`, {
      method: "POST",
    }),
  agents: () => request<Agent[]>("/admin/agents"),
  knowledgeDocs: () => request<KnowledgeDoc[]>("/knowledge/documents"),
  uploadKnowledge: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ id: string; name: string; status: string; chunk_count: number }>(
      "/knowledge/documents",
      { method: "POST", body: form },
    );
  },
  deleteKnowledge: (id: string) =>
    request<{ ok: boolean }>(`/knowledge/documents/${id}`, { method: "DELETE" }),
  knowledgeSearch: (q: string) => request<KnowledgeHit[]>(`/knowledge/search?q=${encodeURIComponent(q)}`),
  strategies: () => request<Strategy[]>("/strategies"),
  strategyEffects: () => request<Strategy[]>("/strategies/effects"),
  recalcEffects: () => request<{ recalculated: number }>("/strategies/recalc-effects", { method: "POST" }),
  createStrategy: (payload: {
    title: string;
    audience?: string;
    hook?: string;
    script?: string;
    task?: string;
    acceptance?: string;
    activity_type?: string;
    channels?: string;
    layers?: string;
    sections?: string;
    kpi_metrics?: string;
    cadence?: string;
    cards?: string;
  }) =>
    request<{ id: string; name: string }>("/strategies", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createStrategyFromInstruction: (id: string) =>
    request<{ id: string; name: string }>(`/strategies/from-instruction/${id}`, {
      method: "POST",
    }),
  strategyTasks: () => request<StrategyTaskItem[]>("/strategies/tasks"),
  dispatchStrategy: (id: string) =>
    request<{ id: string; status: string }>(`/strategies/${id}/dispatch`, { method: "POST" }),
  toggleStrategyManaged: (id: string) =>
    request<{ id: string; managed: boolean; status: string }>(`/strategies/${id}/toggle-managed`, {
      method: "POST",
    }),
  promotePlatform: (strategyId: string) =>
    request<{ id: string; is_platform: boolean }>("/strategies/promote-platform", {
      method: "POST",
      body: JSON.stringify({ strategy_id: strategyId }),
    }),
  createBrandOverride: (platformStrategyId: string, name?: string, params?: Record<string, unknown>) =>
    request<{ id: string; name: string; platform_ref: string }>("/strategies/brand-override", {
      method: "POST",
      body: JSON.stringify({ platform_strategy_id: platformStrategyId, name, params }),
    }),
  runStrategy: (strategyId: string, text?: string) =>
    request<StrategyRunResult>("/strategies/run", {
      method: "POST",
      body: JSON.stringify({ strategy_id: strategyId, text }),
    }),
 llmModels: () => request<LLMModel[]>("/admin/llm/models"),
 llmUsage: () => request<LLMUsage>("/admin/llm/usage"),
  llmPresets: () => request<Record<string, string>[]>("/admin/llm/presets"),
  llmCreateModel: (data: {
    name: string; provider: string; model: string; base_url: string;
    api_key?: string; priority?: number; complexity?: string;
    cost_per_million?: number; enabled?: boolean;
  }) =>
    request<{ id: string }>("/admin/llm/models", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  customers: () => request<CustomerProfile[]>("/customers"),
  customerProfile: (id: string) => request<CustomerProfile>(`/customers/${id}/profile`),
  marketOverview: () => request<MarketOverview>("/market/overview"),
  marketInfluencers: () => request<InfluencerRow[]>("/market/influencers"),
  devBrands: () => request<BrandRow[]>("/dev/brands"),
  devCreateBrand: (name: string, code: string, industryId?: string) =>
    request<{ id: string; name: string; code: string; status: string }>("/dev/brands", {
      method: "POST",
      body: JSON.stringify({ name, code, industry_id: industryId }),
    }),
  devUpdateBrandStatus: (brandId: string, status: string) =>
    request<{ id: string; status: string }>(`/dev/brands/${brandId}/status`, {
      method: "PUT",
      body: JSON.stringify({ status }),
    }),
  devMetering: () => request<MeteringRow[]>("/dev/metering"),
  devMeteringDetail: (brandId: string) => request<MeteringDetail>(`/dev/metering/${brandId}`),
  devAuditLogs: (brandId?: string, action?: string) => {
    const params = new URLSearchParams();
    if (brandId) params.set("brand_id", brandId);
    if (action) params.set("action", action);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request<AuditLogRow[]>(`/dev/audit${qs}`);
  },
 devPlatformAssets: () => request<PlatformAssetOverview>("/dev/platform-assets"),
  devBrandDetail: (brandId: string) => request<BrandDetail>(`/dev/brands/${brandId}`),
  devUpgradePlatformVersion: (version?: string) =>
    request<{ version: string; brands_updated: number; details: { id: string; name: string; old: string | null; new: string }[] }>("/dev/platform-version/upgrade", {
      method: "POST",
      body: JSON.stringify({ version }),
    }),
  devBrandUsers: (brandId: string) => request<BrandUserRow[]>(`/dev/brands/${brandId}/users`),
  devCreateBrandUser: (brandId: string, payload: { username: string; password: string; display_name?: string; role: string }) =>
    request<{ id: string; username: string; role: string; enabled: boolean }>(`/dev/brands/${brandId}/users`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  devUpdateUser: (userId: string, payload: { role?: string; enabled?: boolean }) =>
    request<{ id: string; role: string; enabled: boolean }>(`/dev/users/${userId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
 strategyFeedback: (strategyId: string) =>
    request<FeedbackEventRow[]>(`/strategies/${strategyId}/feedback`),
  strategyEffectBreakdown: (strategyId: string) =>
    request<EffectBreakdown>(`/strategies/${strategyId}/effect-breakdown`),
  feedbackEvents: (limit = 50) =>
    request<FeedbackEventRow[]>(`/strategies/feedback-events/recent?limit=${limit}`),
  // ── P2-2: 跨行業策略復用 + AI 變異 ──
  updateStrategyTags: (strategyId: string, tags: { scenario_tags?: string[]; audience_tags?: string[]; channel_tags?: string[] }) =>
    request<{ id: string; scenario_tags: string[]; audience_tags: string[]; channel_tags: string[] }>(`/strategies/${strategyId}/tags`, {
      method: "PUT",
      body: JSON.stringify(tags),
    }),
  recommendStrategies: (scenario?: string, audience?: string, channel?: string) => {
    const params = new URLSearchParams();
    if (scenario) params.set("scenario", scenario);
    if (audience) params.set("audience", audience);
    if (channel) params.set("channel", channel);
    return request<RecommendRow[]>(`/strategies/recommend?${params}`);
  },
  mutateStrategies: (strategyIds: string[], note?: string) =>
    request<{ id: string; name: string; note: string }>("/strategies/mutate", {
      method: "POST",
      body: JSON.stringify({ strategy_ids: strategyIds, note }),
    }),
  listCandidates: () => request<CandidateRow[]>("/strategies/candidates"),
  approveCandidate: (strategyId: string) =>
    request<{ id: string; name: string; status: string }>(`/strategies/candidates/${strategyId}/approve`, { method: "POST" }),
  rejectCandidate: (strategyId: string) =>
    request<{ id: string; status: string }>(`/strategies/candidates/${strategyId}/reject`, { method: "POST" }),
  marketReportBlocks: () => request<ReportBlockRow[]>("/market/report-blocks"),
  flywheelProducts: () => request<ProductItem[]>("/flywheel/products"),
  createProduct: (payload: Omit<ProductItem, "id">) =>
    request<{ id: string; name: string }>("/flywheel/products", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateProduct: (id: string, payload: Omit<ProductItem, "id">) =>
    request<{ id: string; name: string }>(`/flywheel/products/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteProduct: (id: string) =>
    request<{ ok: boolean }>(`/flywheel/products/${id}`, { method: "DELETE" }),
  importProducts: (items: Omit<ProductItem, "id">[]) =>
    request<{ added: number }>("/flywheel/products/import", {
      method: "POST",
      body: JSON.stringify({ items }),
    }),
  flywheelProductCategories: () => request<ProductCategory[]>("/flywheel/products/categories"),
  flywheelMatches: () => request<MatchItem[]>("/flywheel/matches"),
  runFlywheelMatches: () =>
    request<{ matched: number; demands: number }>("/flywheel/matches/run", { method: "POST" }),
  platformWorkbench: () => request<Workbench>("/platform/workbench"),
  platformTenants: () => request<TenantRow[]>("/platform/tenants"),
  platformIndustries: () => request<IndustryRow[]>("/platform/industries"),
  industryTemplates: (industryId: string, kind?: string) =>
    request<IndustryTemplateRow[]>(
      `/platform/industry-templates?industry_id=${encodeURIComponent(industryId)}${kind ? `&kind=${kind}` : ""}`,
    ),
  updateIndustryTemplate: (id: string, data: Record<string, unknown>, name?: string) =>
    request<{ id: string; kind: string; name: string }>(`/platform/industry-templates/${id}`, {
      method: "PUT",
      body: JSON.stringify({ data, name }),
    }),
  createIndustryTemplate: (payload: {
    industry_id: string;
    kind: string;
    name: string;
    data: Record<string, unknown>;
  }) =>
    request<{ id: string; kind: string }>("/platform/industry-templates", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
 platformInstructions: () => request<InstructionRow[]>("/platform/instructions"),
 onboarding: () =>
   request<{ steps: { key: string; label: string; done: boolean; link: string; detail?: string }[]; total: number; done: number; progress: number }>("/platform/onboarding"),
 createInstruction: (payload: {
    title: string;
    content: string;
    industry_id?: string;
    params?: Record<string, unknown>;
  }) =>
    request<{ id: string; status: string }>("/platform/instructions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
 chatInstruction: (message: string, autoGenerate?: boolean, campaignBrief?: { cards: any[] }) =>
  request<{
    instruction_id: string;
    title: string;
    content: string;
    params: Record<string, unknown>;
    summary: string;
    status: string;
    needs_clarification?: boolean;
    questions?: { dimension: string; question: string; examples: string[] }[];
  }>("/platform/instructions/chat", {
     method: "POST",
      body: JSON.stringify({ message, auto_generate: autoGenerate ?? false, campaign_brief: campaignBrief ?? undefined }),
  }),
  parseCampaignBrief: async (file: File) => {
    const token = localStorage.getItem("pdp_token");
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const tenantId = localStorage.getItem("pdp_tenant_id");
    if (tenantId) headers["X-Tenant-Id"] = tenantId;
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/platform/campaign-brief/parse`, {
      method: "POST",
      headers,
      body: form,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },
  generateInstruction: (id: string) =>
    request<{ id: string; status: string; task_id: string }>(`/platform/instructions/${id}/generate`, {
      method: "POST",
    }),
  approveInstruction: (id: string) =>
    request<{ id: string; status: string; tasks: number }>(`/platform/instructions/${id}/approve`, {
      method: "POST",
    }),
  rejectInstruction: (id: string) =>
    request<{ id: string; status: string }>(`/platform/instructions/${id}/reject`, { method: "POST" }),
  acceptInstruction: (id: string, payload?: { kpi_results?: Record<string, string | number> }) =>
    request<{ id: string; status: string; report_id: string }>(`/platform/instructions/${id}/accept`, {
      method: "POST",
      body: payload ? JSON.stringify(payload) : undefined,
    }),
  exportInstruction: async (id: string) => {
    const token = localStorage.getItem("pdp_token");
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const tenantId = localStorage.getItem("pdp_tenant_id");
    if (tenantId) headers["X-Tenant-Id"] = tenantId;
    const res = await fetch(`${BASE}/platform/instructions/${id}/export`, { headers });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename\*=UTF-8''(.+)/);
    const filename = match ? decodeURIComponent(match[1]) : "资料包.xlsx";
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
   URL.revokeObjectURL(url);
 },
  getCampaignBrief: (id: string) =>
    request<{ instruction_id: string; campaign_brief: { cards?: any[]; source?: string; count?: number } }>(
      `/platform/instructions/${id}/campaign-brief`,
    ),
  saveCampaignBrief: (id: string, payload: { cards: any[] }) =>
    request<{ status: string }>(`/platform/instructions/${id}/campaign-brief`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  uploadCampaignBrief: async (id: string, file: File) => {
    const token = localStorage.getItem("pdp_token");
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const tenantId = localStorage.getItem("pdp_tenant_id");
    if (tenantId) headers["X-Tenant-Id"] = tenantId;
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/platform/instructions/${id}/campaign-brief/upload`, {
      method: "POST",
      headers,
      body: form,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },
 exportExecution: async () => {
    const token = localStorage.getItem("pdp_token");
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const tenantId = localStorage.getItem("pdp_tenant_id");
    if (tenantId) headers["X-Tenant-Id"] = tenantId;
    const res = await fetch(`${BASE}/platform/execution/export`, { headers });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename\*=UTF-8''(.+)/);
    const filename = match ? decodeURIComponent(match[1]) : "执行中心.xlsx";
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },
  platformExecution: () => request<ExecutionCenterData>("/platform/execution"),
  platformReport: (id: string) => request<ReportDetail>(`/platform/reports/${id}`),
  updateExecutionTodo: (id: string, payload: { due_at?: string; due_time?: string; content?: string; status?: string }) =>
    request<{ id: string; channel: string; due_at: string | null; due_time?: string; content: string | null; status: string }>(
      `/platform/execution/todos/${id}`,
      { method: "PUT", body: JSON.stringify(payload) },
    ),
  dispatchExecutionTodo: (id: string) =>
    request<{ id: string; status: string; message_id?: string; guardrail?: { matched_rule: string; note: string } }>(
      `/platform/execution/todos/${id}/dispatch`,
      { method: "POST" },
    ),
  rebuildInstructionPlan: (id: string) =>
    request<{ id: string; todo_count: number }>(`/platform/instructions/${id}/plan/rebuild`, {
      method: "POST",
    }),
  runPlanScheduler: () =>
    request<{ dispatched: number; missed: number }>("/platform/execution/scheduler/run", {
      method: "POST",
    }),
  sendPolicy: () => request<SendPolicy>("/platform/send-policy"),
  updateSendPolicy: (payload: Partial<SendPolicy>) =>
    request<SendPolicy>("/platform/send-policy", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  toggleInstructionPlanPause: (id: string) =>
    request<{ id: string; plan_paused: boolean }>(`/platform/instructions/${id}/plan/pause`, {
      method: "POST",
    }),
  platformSearch: (q: string) => request<SearchResult>(`/platform/search?q=${encodeURIComponent(q)}`),
  platformDataSources: () => request<DataSourceRow[]>("/platform/data-sources"),
  platformApiExamples: () => request<ApiExampleRow[]>("/platform/api-examples"),
  checkChannel: (text: string) =>
    request<ChannelCheckResult>("/platform/check-channel", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  platformCockpit: () => request<Cockpit>("/platform/cockpit"),
  platformIntegrations: () => request<IntegrationRow[]>("/platform/integrations"),
  platformApiLogs: () => request<ApiLogRow[]>("/platform/api-logs"),
  platformOpsChannels: () => request<OpsChannelRow[]>("/platform/ops-channels"),
  platformAlerts: () => request<AlertRow[]>("/platform/alerts"),
  resolveAlert: (id: string) =>
    request<{ id: string; resolved: boolean }>(`/platform/alerts/${id}/resolve`, { method: "POST" }),
  platformCampaigns: () => request<CampaignRow[]>("/platform/campaigns"),
  platformFissionTemplates: () => request<FissionTemplateRow[]>("/platform/fission-templates"),
  platformReports: () => request<ReportDocRow[]>("/platform/reports"),
  generateReport: () =>
    request<{ id: string; title: string }>("/platform/reports/generate", { method: "POST" }),
  getReport: (id: string) => request<ReportDetail>(`/platform/reports/${id}`),
  createFeedback: (payload: {
    task_id?: string;
    action: string;
    amount?: number;
    note?: string;
    occurred_at?: string;
  }) =>
    request<{ id: string; action: string }>("/platform/feedback", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
 updateTaskStatus: (id: string, status: string) =>
   request<{ id: string; status: string }>(`/platform/tasks/${id}/status`, {
     method: "POST",
     body: JSON.stringify({ status }),
   }),
  feishuMessages: (limit = 10) =>
    request<FeishuMessageRow[]>(`/feishu/messages?limit=${limit}`),
  feishuSend: (text: string) =>
    request<FeishuSendResult>("/feishu/send", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  feishuHandle: (text: string) =>
    request<FeishuHandleResult>("/feishu/handle", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
 feishuSummary: () => request<FeishuSummary>("/feishu/summary"),
  feishuDailyBriefs: () => request<DailyBriefs>("/feishu/daily-briefs"),
 feishuTriggerBrief: (report_type: "morning" | "evening") =>
   request<Record<string, unknown>>("/feishu/trigger-brief", {
     method: "POST",
     body: JSON.stringify({ report_type }),
   }),
  feishuConfig: () => request<FeishuConfigRow>("/feishu/config"),
  updateFeishuConfig: (config: Partial<FeishuConfigRow>) =>
    request<{ ok: boolean; detail: string }>("/feishu/config", {
      method: "PUT",
      body: JSON.stringify(config),
    }),
  testFeishu: () =>
    request<FeishuTestResult>("/feishu/test", { method: "POST" }),
};
