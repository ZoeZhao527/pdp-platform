export interface Overview {
  conversations: number;
  messages: number;
  signals: number;
  flywheel_cycles: number;
  guardrail_hits: number;
  llm_calls: number;
  flywheel: {
    total_cycles: number;
    avg_closed_loop_days: number;
    total_hit_count: number;
    total_adopted_count: number;
    avg_roi: number;
  };
  recent_conversations: Conversation[];
}

export interface Conversation {
  id: string;
  external_id: string;
  channel_id: string;
  conversation_type: "cs" | "ops";
  status: string;
  title: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface Message {
  id: string;
  direction: "in" | "out";
  source: string;
  content: string;
  created_at: string | null;
}

export interface FlywheelDashboard {
  total_cycles: number;
  avg_closed_loop_days: number;
  total_hit_count: number;
  total_adopted_count: number;
  avg_roi: number;
  recent_cycles: FlywheelCycle[];
}

export interface FlywheelStatus {
  pending_signals: number;
  topic_signals: number;
  auto_enabled: boolean;
  last_run: {
    time: string | null;
    sources: { source: string; ok: boolean; count?: number; error?: string }[];
  } | null;
}

export interface FlywheelSignal {
  id: string;
  source_type: string;
  raw_content: string;
  status: string;
  customer_id: string | null;
  created_at: string | null;
}

export interface DemandProfileRow {
  id: string;
  signal_id: string;
  scenario: string;
  tags: Record<string, unknown> | null;
  intensity: number;
  verified: boolean;
  created_at: string | null;
}

export interface FlywheelExecution {
  id: string;
  strategy_id: string | null;
  status: string;
  result: {
    reply?: string;
    matched_capabilities?: string[];
    model?: string;
  } | null;
  metrics: {
    closed_loop_days?: number;
    hit_count?: number;
    adopted_count?: number;
    roi?: number;
  } | null;
  created_at: string | null;
}

export interface MarketOverview {
  influencers: number;
  hot_videos: number;
  report_blocks: number;
  platforms: Record<string, number>;
  top_influencers: number;
}

export interface InfluencerRow {
  id: string;
  name: string;
  platform: string;
  fans: number;
  avg_plays: number;
  interaction_rate: number;
  verticality: number;
  gmv: number;
  conversion_rate: number;
  risk: number;
  score: number;
  grade: string;
  level_label: string | null;
  fit_projects: string | null;
  budget: string | null;
  competitors: string | null;
  suggestion: string;
  notes: string | null;
}

export interface ReportBlockRow {
  block: string;
  title: string | null;
  data: Record<string, unknown> | null;
}

export interface FlywheelCycle {
  id: string;
  status: string;
  strategy_id: string | null;
  result: {
    reply?: string;
    matched_capabilities?: string[];
    model?: string;
  } | null;
  metrics: {
    closed_loop_days?: number;
    hit_count?: number;
    adopted_count?: number;
    roi?: number;
  } | null;
  created_at: string | null;
}

export interface GuardrailHit {
  id: string;
  content: string;
  action: string;
  note: string | null;
  created_at: string | null;
}

export interface GuardrailRule {
  id: string;
  name: string;
  rule_type: string;
  action: string;
  pattern: string[];
  enabled: boolean;
}

export interface Channel {
  id: string;
  name: string;
  channel_type: string;
  enabled: boolean;
  config: Record<string, unknown> | null;
}

export interface Agent {
  key: string;
  name: string;
  description: string | null;
  enabled: boolean;
}

export interface KnowledgeDoc {
  id: string;
  name: string;
  file_type: string;
  status: string;
  chunk_count: number;
  size_bytes: number;
  created_at: string | null;
}

export interface KnowledgeHit {
  id: string;
  doc_id: string;
  content: string;
  score: number;
  metadata: Record<string, unknown> | null;
}

export interface Strategy {
  id: string;
  name: string;
  strategy_type: string;
  agent_key: string;
  params: Record<string, unknown> | null;
  status: string;
  managed: boolean;
  enabled: boolean;
  score: number;
  runs: number;
  wins: number;
  feedback_count: number;
  last_kpi: Record<string, unknown> | null;
 is_platform: boolean;
 platform_ref: string | null;
  scenario_tags: string[];
  audience_tags: string[];
  channel_tags: string[];
  is_candidate: boolean;
  candidate_status: string;
  parent_ids: string[];
  mutation_note: string;
}

export interface StrategyTaskItem {
  id: string;
  strategy_id: string | null;
  title: string;
  channel: string | null;
  audience: string | null;
  acceptance: string | null;
  status: string;
  due_at: string | null;
}

export interface StrategyRunResult {
  agent: string;
  reply: string;
  model: string;
  provider: string;
}

export interface CandidateRow {
  id: string;
  name: string;
  candidate_status: string;
  mutation_note: string;
  parent_names: string[];
  scenario_tags: string[];
  audience_tags: string[];
  channel_tags: string[];
  params: Record<string, unknown> | null;
  score: number;
  created_at: string | null;
}

export interface RecommendRow {
  id: string;
  name: string;
  strategy_type: string;
  score: number;
  runs: number;
  wins: number;
  industry_id: string | null;
  scenario_tags: string[];
  audience_tags: string[];
  channel_tags: string[];
  similarity: number;
  params: Record<string, unknown> | null;
}


export interface Workbench {
  counts: {
    signals: number;
    demands: number;
    products: number;
    matches: number;
    strategies: number;
    tasks: number;
    instructions: number;
  };
  todos: {
    pending_signals: number;
    unresolved_alerts: number;
    pending_approvals: number;
  };
  kpi: {
    metric: string;
    target: number;
    actual: number;
    week: string;
    lower_better: boolean;
    note: string | null;
  }[];
  recent_signals: {
    id: string;
    source_type: string;
    raw_content: string;
    status: string;
  }[];
  recent_executions: {
    id: string;
    status: string;
    reply: string;
  }[];
}

export interface IndustryRow {
  id: string;
  code: string;
  name: string;
  description: string | null;
}

export interface IndustryTemplateRow {
  id: string;
  kind: string;
  name: string;
  data: Record<string, unknown> | null;
}

export interface InstructionRow {
  id: string;
  title: string;
  content: string;
  status: string;
  industry_id: string | null;
  created_by: string;
  strategy_ids: Record<string, unknown> | null;
  asset: AssetPackage | null;
  params: Record<string, unknown> | null;
  created_at: string | null;
}

export interface ActivityType {
  name: string;
  mechanism: string;
  products: string[];
  rhythm: { phase: string; days: string; actions: string }[];
  target_audience: string;
}

export interface AssetPackage {
  activity_plan: {
    theme: string;
    types: ActivityType[] | string[];
    channels: string[];
    budget: string;
    goal?: string;
    kpi: string[];
    timeline?: string;
  };
  activity_details?: {
    summary?: string;
    calendar?: string;
    reference?: string;
  };
  product_mix: {
    name: string;
    category: string | null;
    price: number;
    role: string;
    target: string;
  }[];
  card_structure?: {
    summary?: string;
    rules?: string;
    reference?: string;
    items?: { name: string; price: string; role: string; target: string; selling_point: string }[];
    cards?: {
      card_type: string;
      card_name: string;
      zones?: { zone: string; tier: string; items: { name: string; price: number }[]; pick_rule: string }[];
      total_retail?: number;
      selling_price?: number;
      discount?: string;
      compliance?: string;
      selling_point?: string;
    }[];
  };
  audience?: {
    layers: string[];
    tags: string[];
    age: string;
    city: string;
    source: string;
  };
  sales_playbook: {
    sections: string[];
    objections: { issue: string; response: string; tone: string; scenario: string }[];
    layer_plays: { layer: string; goal: string; action: string; script: string; follow_up: string }[];
    tone?: string;
    follow_up?: string;
  };
  script_templates?: {
    opening?: string;
    close?: string;
    objection?: string;
    follow_up?: string;
    reference?: string;
    objection_handling?: { scenario: string; category?: string; response: string }[];
    layered_scripts?: { layer: string; opening: string; close: string; follow_up: string }[];
  };
  content_schedule: {
    channels: string[];
    materials: { type: string; title: string; copy: string; channel: string; purpose: string }[];
    schedules: { channel: string; cadence: string; time_slots: string; content_type: string; goal: string }[];
    frequency?: string;
    daily_content?: { day: string; channel: string; content: string }[];
  };
  content_materials?: {
    summary?: string;
    reference?: string;
  };
  kpi_targets: string[];
  constraints?: {
    forbidden_words: string;
    review: string;
    budget_limit: string;
    time_limit: string;
    automation_mode: string;
    schedule: string;
  };
}

export interface TenantRow {
  id: string;
  name: string;
  code: string;
  industry_id: string | null;
}

export interface AuthUser {
  id: string;
  username: string;
  display_name: string | null;
  role: string;
  enabled: boolean;
  tenant_id: string;
}

export interface LoginResult {
  token: string;
  user: AuthUser;
  industry_id: string | null;
}

export interface SearchResult {
  signals: { id: string; content: string; type: string }[];
  strategies: { id: string; content: string; type: string }[];
  tasks: { id: string; content: string; type: string }[];
}

export interface DataSourceRow {
  source: string;
  count: number;
}

export interface ApiExampleRow {
  method: string;
  path: string;
  purpose: string;
  example: string;
}

export interface ChannelCheckResult {
  passed: boolean;
  hits: { source: string; rule: string; keyword: string; action: string }[];
}

export interface Cockpit {
  topics: number;
  influencers: number;
  execution_status: Record<string, number>;
  hot_topics: { id: string; keyword: string; status: string }[];
  kpi: {
    metric: string;
    target: number;
    actual: number;
    week: string;
    note: string | null;
  }[];
}

export interface ProductItem {
  id: string;
  name: string;
  category: string | null;
  price: number;
  price_band?: string | null;
  efficacy: string[];
  segments: string[];
  seasons: string[];
  description?: string | null;
  is_focus: boolean;
}

export interface ProductCategory {
  category: string;
  count: number;
}

export interface MatchItem {
  id: string;
  demand_scenario: string;
  demand_tags: string[];
  product_name: string;
  product_category: string | null;
  score: number;
  reasons: string[];
}

export interface IntegrationRow {
  id: string;
  name: string;
  kind: string;
  api_key: string;
  enabled: boolean;
}

export interface ApiLogRow {
  id: string;
  path: string;
  method: string;
  status: number;
  created_at: string | null;
}

export interface OpsChannelRow {
  id: string;
  name: string;
  kind: string;
  enabled: boolean;
  timeout_seconds: number;
  follow_up_hours: number;
  sensitive_words: string | null;
}

export interface AlertRow {
  id: string;
  alert_type: string;
  message: string;
  resolved: boolean;
  created_at: string | null;
}

export interface CampaignRow {
  id: string;
  name: string;
  channel: string | null;
  budget: number;
  target_leads: number;
  status: string;
  start_at: string | null;
  end_at: string | null;
}

export interface FissionTemplateRow {
  id: string;
  name: string;
  description: string | null;
  channel: string | null;
  reward: string | null;
  rule: string | null;
}

export interface ReportDocRow {
  id: string;
  kind: string;
  title: string;
  created_at: string | null;
}

export interface ReportDetail extends ReportDocRow {
  content: string;
}

export interface ExecutionTaskRow {
  id: string;
  instruction_id: string | null;
  instruction_title: string;
  instruction_status: string;
  title: string;
  channel: string;
  status: string;
  due_at: string | null;
  message_id: string | null;
  content: string;
  guardrail?: { matched_rule: string; note: string } | null;
  todo?: boolean;
  due_time?: string;
  created_at: string | null;
}

export interface ManagedTaskRow {
  id: string;
  title: string;
  channel: string;
  status: string;
  due_at: string | null;
  message_id: string | null;
  content: string;
  due_time?: string;
  todo?: boolean;
  created_at: string | null;
}

export interface ExecutionInstructionBoard {
  id: string;
  title: string;
  status: string;
  asset: AssetPackage | null;
  tasks: ExecutionTaskRow[];
  plan_paused?: boolean;
  kpi_results?: Record<string, number | string> | null;
  goal_value?: string | null;
}

export interface ExecutionCenterData {
  tasks: ExecutionTaskRow[];
  managed_tasks: ManagedTaskRow[];
  reports: ReportDocRow[];
  alerts: AlertRow[];
  instructions: ExecutionInstructionBoard[];
}

export interface SendPolicy {
  auto_enabled: boolean;
  window_start: string;
  window_end: string;
  grace_hours: number;
  max_per_day: Record<string, number>;
  paused_channels: string[];
}

export interface FlywheelSuggestion {
  id: string;
  kind: "signal" | "demand" | "match" | "strategy";
  title: string;
  summary: string;
  params: Record<string, string>;
}

export interface FlywheelAdvisories {
  signals: {
    id: string;
    source_type: string;
    raw_content: string;
    status: string;
    created_at: string | null;
  }[];
  demands: {
    scenario: string;
    tags: string[];
    count: number;
    intensity: number;
    evidence: string;
  }[];
  matches: {
    demand_scenario: string;
    demand_tags: string[];
    product_name: string;
    product_category: string | null;
    score: number;
    reasons: string[];
  }[];
  strategies: {
    id: string;
    name: string;
    strategy_type: string;
    status: string;
    managed: boolean;
    next_run_at: string | null;
    score: number;
    runs: number;
    wins: number;
    feedback_count: number;
    is_platform: boolean;
    platform_ref: string | null;
  }[];
  suggestions: FlywheelSuggestion[];
}

export interface LLMModel {
  id: string;
  name: string;
  provider: string;
  model: string;
  base_url: string;
  priority: number;
  complexity: string;
  cost_per_million: number;
  enabled: boolean;
  has_key: boolean;
}

export interface LLMBudgetRow {
  id: string;
  period_type: string;
  period_key: string;
  token_limit: number;
  tokens_used: number;
  cost_limit: number;
  cost_used: number;
}

export interface LLMCallLogRow {
  id: string;
  model: string;
  provider: string;
  prompt_tokens: number;
  completion_tokens: number;
  latency_ms: number;
  cost: number;
  status: string;
  error: string | null;
  created_at: string | null;
}

export interface LLMUsage {
  budgets: LLMBudgetRow[];
  logs: LLMCallLogRow[];
}

export interface CustomerProfile {
  id: string;
  one_id: string;
  name: string | null;
  profile: Record<string, unknown>;
  created_at: string | null;
}

export interface WebhookResult {
  conversation_id: string;
  route: "cs" | "ops";
  reply: string | null;
  handoff: boolean;
}

export interface FeishuMessageRow {
  message_id: string;
  sender: string;
  sender_id: string;
  text: string;
  created_at: string;
  raw_timestamp: string;
  msg_type: string;
  is_system: boolean;
}

export interface FeishuSummary {
  today_feedback_count: number;
  action_breakdown: Record<string, number>;
  total_amount: number;
  feedback_items: { action: string; amount: number; note: string; occurred_at: string }[];
}

export interface FeishuSendResult {
  ok: boolean;
  message_id: string;
  detail: string;
}

export interface FeishuHandleResult {
  reply: string;
}

export interface FeishuConfigRow {
  app_id: string;
  app_secret: string;
  chat_id: string;
  verification_token: string;
  encrypt_key: string;
  enabled: boolean;
  messaging_enabled: boolean;
  configured: boolean;
}

export interface FeishuTestResult {
  ok: boolean;
  detail: string;
}

export interface DailyBriefReport {
  content: string;
  sent: boolean;
  sent_at: string | null;
  payload: Record<string, unknown> | null;
}

export interface DailyBriefTask {
  id: string;
  title: string;
  channel: string;
  due_time: string;
  audience: string;
}

export interface DailyBriefs {
  morning: DailyBriefReport | null;
  evening: DailyBriefReport | null;
  pending_tasks: DailyBriefTask[];
}

export interface BrandRow {
  id: string;
  name: string;
  code: string;
  industry_id: string | null;
  status: string;
  platform_version: string | null;
  created_at: string | null;
  stats: {
    strategies: number;
    messages: number;
    llm_calls: number;
    llm_tokens: number;
    llm_cost: number;
    users: number;
  };
}

export interface MeteringRow {
  brand_id: string;
  brand_name: string;
  llm_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  llm_cost: number;
  avg_latency_ms: number;
  api_calls: number;
  tasks: number;
}

export interface MeteringDetail {
  brand_id: string;
  brand_name: string;
  logs: {
    id: string;
    model: string;
    provider: string;
    prompt_tokens: number;
    completion_tokens: number;
    cost: number;
    latency_ms: number;
    status: string;
    error: string | null;
    created_at: string | null;
  }[];
}

export interface AuditLogRow {
  id: string;
  tenant_id: string;
  actor: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  created_at: string | null;
}

export interface PlatformAssetOverview {
  strategies: { platform: number; names: string[] };
  guardrails: { platform: number; names: string[] };
  knowledge: { platform: number };
  brands: number;
}

export interface BrandDetail {
  id: string;
  name: string;
  code: string;
  industry_id: string | null;
  status: string;
  platform_version: string | null;
  created_at: string | null;
  agents: { id: string; key: string; name: string; description: string | null; enabled: boolean }[];
  channels: { id: string; name: string; channel_type: string; enabled: boolean }[];
  kpis: { id: string; week: string; metric: string; target: number; actual: number; lower_better: boolean }[];
  users: BrandUserRow[];
  llm_configs: { id: string; name: string; provider: string; model: string; priority: number; complexity: string; enabled: boolean }[];
  prompt_templates: { id: string; key: string; version: number; enabled: boolean }[];
  knowledge: { doc_count: number; chunk_count: number; total_size: number };
  feishu: { configured: boolean; enabled: boolean };
  strategies_count: number;
}

export interface BrandUserRow {
  id: string;
  username: string;
  display_name: string | null;
  role: string;
  enabled: boolean;
  created_at: string | null;
}

export interface FeedbackEventRow {
  id: string;
  action: string;
  amount: number;
  note: string;
  strategy_id: string | null;
  strategy_name: string;
  occurred_at: string | null;
  created_at: string | null;
}

export interface EffectBreakdown {
  id: string;
  name: string;
  score: number;
  components: {
    kpi_achievement: number;
    win_rate: number;
    feedback_signal: number;
  };
  weights: { kpi: number; win_rate: number; feedback: number };
  runs: number;
  wins: number;
  feedback_count: number;
  last_kpi: Record<string, unknown> | null;
}
