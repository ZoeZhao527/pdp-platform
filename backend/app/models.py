from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def new_id() -> str:
    return str(uuid4())


class TimestampMixin:
    industry_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    industry_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active", nullable=False)
    platform_version: Mapped[str | None] = mapped_column(String(32), nullable=True)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    role: Mapped[str] = mapped_column(String(16), default="operator", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Industry(Base, TimestampMixin):
    __tablename__ = "industries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class IndustryTemplate(Base, TimestampMixin):
    __tablename__ = "industry_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    industry_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # activity / catalog / sales / content / kpi
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    data_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Channel(Base, TimestampMixin):
    __tablename__ = "channels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(32), nullable=False)
    config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    channel_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    conversation_type: Mapped[str] = mapped_column(String(16), default="ops", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    conversation_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    source: Mapped[str] = mapped_column(String(24), default="channel", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    channel_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    one_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    profile_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class DemandSignal(Base, TimestampMixin):
    __tablename__ = "demand_signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_type: Mapped[str] = mapped_column(String(24), default="message", nullable=False)
    segment: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="new", nullable=False)


class DemandProfile(Base, TimestampMixin):
    __tablename__ = "demand_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    signal_id: Mapped[str] = mapped_column(String(36), nullable=False)
    tags_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scenario: Mapped[str | None] = mapped_column(String(120), nullable=True)
    intensity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, server_default="0", nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)


class DemandGraph(Base, TimestampMixin):
    __tablename__ = "demand_graph"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    demand_key: Mapped[str] = mapped_column(String(120), nullable=False)
    scenario: Mapped[str | None] = mapped_column(String(120), nullable=True)
    related_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_profile_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class Capability(Base, TimestampMixin):
    __tablename__ = "capabilities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    industry: Mapped[str] = mapped_column(String(64), nullable=False)
    product: Mapped[str] = mapped_column(String(120), nullable=False)
    capability: Mapped[str] = mapped_column(String(200), nullable=False)
    price: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    price_band: Mapped[str | None] = mapped_column(String(64), nullable=True)
    efficacy_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    segments_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    seasons_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_focus: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    match_rules_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class MatchResult(Base, TimestampMixin):
    __tablename__ = "match_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    demand_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    product_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reasons_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Strategy(Base, TimestampMixin):
    __tablename__ = "strategies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    strategy_type: Mapped[str] = mapped_column(String(32), nullable=False)
    agent_key: Mapped[str] = mapped_column(String(64), default="ops_assistant", nullable=False)
    params_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="草稿", server_default="草稿", nullable=False)
    managed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    run_cycle: Mapped[int] = mapped_column(Integer, default=1440, server_default="1440", nullable=False)
    last_run_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    next_run_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    industry_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    runs: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    wins: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, server_default="0.0", nullable=False)
    feedback_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    last_kpi_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_platform: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    platform_ref: Mapped[str | None] = mapped_column(String(36), nullable=True)
    scenario_tags_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    audience_tags_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    channel_tags_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_candidate: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    candidate_status: Mapped[str] = mapped_column(String(16), default="", server_default="", nullable=False)
    parent_ids_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    mutation_note: Mapped[str | None] = mapped_column(String(500), nullable=True)


class StrategyExecution(Base, TimestampMixin):
    __tablename__ = "strategy_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    strategy_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    demand_profile_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metrics_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class FlywheelMetric(Base, TimestampMixin):
    __tablename__ = "flywheel_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    cycle_id: Mapped[str] = mapped_column(String(36), nullable=False)
    closed_loop_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    adopted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    roi: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    snapshot_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ToolRegistry(Base, TimestampMixin):
    __tablename__ = "tool_registry"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    schema_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AgentDef(Base, TimestampMixin):
    __tablename__ = "agent_defs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    prompt_template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AgentRun(Base, TimestampMixin):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    agent_def_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    input_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="done", nullable=False)


class LLMModelConfig(Base, TimestampMixin):
    __tablename__ = "llm_model_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    complexity: Mapped[str] = mapped_column(String(16), default="complex", nullable=False)
    cost_per_million: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class LLMBudget(Base, TimestampMixin):
    __tablename__ = "llm_budgets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    period_type: Mapped[str] = mapped_column(String(16), nullable=False)  # daily / monthly
    period_key: Mapped[str] = mapped_column(String(32), nullable=False)  # 2026-08-14 / 2026-08
    token_limit: Mapped[int] = mapped_column(Integer, default=1_000_000, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_limit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cost_used: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class LLMCallLog(Base, TimestampMixin):
    __tablename__ = "llm_call_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ok", nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class PromptTemplate(Base, TimestampMixin):
    __tablename__ = "prompt_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class GuardrailRule(Base, TimestampMixin):
    __tablename__ = "guardrail_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    pattern_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    action: Mapped[str] = mapped_column(String(16), default="block", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_platform: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    platform_ref: Mapped[str | None] = mapped_column(String(36), nullable=True)


class GuardrailHit(Base, TimestampMixin):
    __tablename__ = "guardrail_hits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    rule_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)


class KnowledgeDoc(Base, TimestampMixin):
    __tablename__ = "knowledge_docs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class KnowledgeChunk(Base, TimestampMixin):
    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    doc_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_platform: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    platform_ref: Mapped[str | None] = mapped_column(String(36), nullable=True)
    tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Influencer(Base, TimestampMixin):
    __tablename__ = "influencers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), default="抖音", nullable=False)
    fans: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_plays: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    likes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shares: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    interaction_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    verticality: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    gmv: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    conversion_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    risk: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    grade: Mapped[str] = mapped_column(String(16), default="C", nullable=False)
    suggestion: Mapped[str] = mapped_column(String(32), default="观察", nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="demo", nullable=False)
    level_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    fit_projects: Mapped[str | None] = mapped_column(String(255), nullable=True)
    budget: Mapped[str | None] = mapped_column(String(120), nullable=True)
    competitors: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class HotVideo(Base, TimestampMixin):
    __tablename__ = "hot_videos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    influencer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    influencer_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    category: Mapped[str] = mapped_column(String(64), default="短视频种草", nullable=False)
    plays: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    likes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shares: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    heat: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    tags: Mapped[str | None] = mapped_column(String(255), nullable=True)
    related_demand: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="demo", nullable=False)


class ReportBlock(Base, TimestampMixin):
    __tablename__ = "report_blocks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    block: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    data_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class KpiMetric(Base, TimestampMixin):
    __tablename__ = "kpi_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    week: Mapped[str] = mapped_column(String(16), nullable=False)
    metric: Mapped[str] = mapped_column(String(120), nullable=False)
    target: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    actual: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    lower_better: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Integration(Base, TimestampMixin):
    __tablename__ = "integrations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    api_key: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class StrategyTask(Base, TimestampMixin):
    __tablename__ = "strategy_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    instruction_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    strategy_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    channel: Mapped[str | None] = mapped_column(String(64), nullable=True)
    audience: Mapped[str | None] = mapped_column(String(255), nullable=True)
    script: Mapped[str | None] = mapped_column(Text, nullable=True)
    acceptance: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="待执行", nullable=False)
    external_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    due_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Instruction(Base, TimestampMixin):
    __tablename__ = "instructions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    industry_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="待处理", nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="运营", nullable=False)
    strategy_ids_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    asset_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    params_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    campaign_brief_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class FeedbackEvent(Base, TimestampMixin):
    __tablename__ = "feedback_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    strategy_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ApiLog(Base, TimestampMixin):
    __tablename__ = "api_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    integration_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[int] = mapped_column(Integer, default=200, nullable=False)


class Alert(Base, TimestampMixin):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    alert_type: Mapped[str] = mapped_column(String(32), default="跟进", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class OpsChannel(Base, TimestampMixin):
    __tablename__ = "ops_channels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="企微", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=3600, nullable=False)
    follow_up_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    sensitive_words: Mapped[str | None] = mapped_column(Text, nullable=True)


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    channel: Mapped[str | None] = mapped_column(String(64), nullable=True)
    budget: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    target_leads: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="草稿", nullable=False)
    start_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    end_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class FissionTemplate(Base, TimestampMixin):
    __tablename__ = "fission_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reward: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rule: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReportDoc(Base, TimestampMixin):
    __tablename__ = "report_docs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="周报", nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    actor: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    before_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

class DailyReport(Base, TimestampMixin):
    """早九晚六定时简报：晨间任务清单 + 晚间运营日报。"""

    __tablename__ = "daily_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    report_date: Mapped[str] = mapped_column(String(10), nullable=False)
    report_type: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sent_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class FeishuConfig(Base, TimestampMixin):
    """飞书自建应用配置：每个品牌独立一套 app_id/secret/chat_id。"""

    __tablename__ = "feishu_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)
    app_id: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    app_secret: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    chat_id: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    verification_token: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    encrypt_key: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    messaging_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
