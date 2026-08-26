"""开发者管理后台 API

P2-1：品牌分支机制 —— 一键派生品牌 + 平台版本升级 + 用户管理
全部 admin 权限，跨租户视角。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import Runtime, get_runtime
from app.auth import hash_password, require_roles
from app.config import get_settings
from app.db import get_db
from app.models import (
    AgentDef,
    ApiLog,
    AuditLog,
    Channel,
    Conversation,
    FeishuConfig,
    GuardrailRule,
    KnowledgeChunk,
    KnowledgeDoc,
    KpiMetric,
    LLMCallLog,
    LLMModelConfig,
    Message,
    PromptTemplate,
    Strategy,
    StrategyTask,
    Tenant,
    ToolRegistry,
    User,
)

router = APIRouter(prefix="/api/v1/dev", tags=["dev-console"])

DEFAULT_SOURCE_TENANT = "tenant-default"
PLATFORM_CURRENT_VERSION = "2.0"

# ── 品牌管理 ──────────────────────────────────────────────


@router.get("/brands")
def list_brands(
    db=Depends(get_db),
    _auth: dict = Depends(require_roles("admin")),
) -> list[dict]:
    """列出所有品牌（租户），含策略数、消息数、LLM 调用统计。"""
    rows = db.query(Tenant).order_by(Tenant.created_at.asc()).all()
    result = []
    for t in rows:
        strategy_count = db.query(Strategy).filter(
            Strategy.tenant_id == t.id, Strategy.is_platform == False  # noqa: E712
        ).count()
        platform_strategy_count = db.query(Strategy).filter(
            Strategy.is_platform == True  # noqa: E712
        ).count()
        msg_count = db.query(Message).filter(Message.tenant_id == t.id).count()
        llm_calls = db.query(
            func.count(LLMCallLog.id),
            func.sum(LLMCallLog.prompt_tokens + LLMCallLog.completion_tokens),
            func.sum(LLMCallLog.cost),
        ).filter(LLMCallLog.tenant_id == t.id).one()
        user_count = db.query(User).filter(User.tenant_id == t.id).count()
        result.append({
            "id": t.id,
            "name": t.name,
            "code": t.code,
            "industry_id": t.industry_id,
            "status": t.status,
            "platform_version": t.platform_version,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "stats": {
                "strategies": strategy_count,
                "messages": msg_count,
                "llm_calls": llm_calls[0] or 0,
                "llm_tokens": int(llm_calls[1] or 0),
                "llm_cost": round(float(llm_calls[2] or 0), 4),
                "users": user_count,
            },
        })
    return result


class BrandCreateIn(BaseModel):
    name: str
    code: str
    industry_id: str | None = None


def _init_brand_infrastructure(db, tenant_id: str, industry_id: str | None) -> dict:
    """为新品牌一键复制基础设施：Agent / Channel / KPI / PromptTemplate / LLMConfig / ToolRegistry"""
    source = DEFAULT_SOURCE_TENANT
    report: dict[str, int] = {}

    # 1. AgentDef
    src_agents = db.query(AgentDef).filter(AgentDef.tenant_id == source).all()
    for a in src_agents:
        db.add(AgentDef(
            tenant_id=tenant_id, key=a.key, name=a.name, description=a.description, enabled=True,
        ))
    report["agents"] = len(src_agents)

    # 2. PromptTemplate
    src_templates = db.query(PromptTemplate).filter(PromptTemplate.tenant_id == source).all()
    for t in src_templates:
        db.add(PromptTemplate(
            tenant_id=tenant_id, key=t.key, content=t.content, version=t.version, enabled=True,
        ))
    report["prompt_templates"] = len(src_templates)

    # 3. LLMModelConfig
    src_configs = db.query(LLMModelConfig).filter(LLMModelConfig.tenant_id == source).all()
    for c in src_configs:
        db.add(LLMModelConfig(
            tenant_id=tenant_id, name=c.name, provider=c.provider, model=c.model,
            base_url=c.base_url, api_key=c.api_key, priority=c.priority,
            complexity=c.complexity, cost_per_million=c.cost_per_million, enabled=True,
        ))
    report["llm_configs"] = len(src_configs)

    # 4. ToolRegistry
    src_tools = db.query(ToolRegistry).filter(ToolRegistry.tenant_id == source).all()
    for t in src_tools:
        db.add(ToolRegistry(
            tenant_id=tenant_id, name=t.name, description=t.description, schema_json=t.schema_json, enabled=True,
        ))
    report["tools"] = len(src_tools)

    # 5. Channel (mock + wecom)
    src_channels = db.query(Channel).filter(Channel.tenant_id == source).all()
    for ch in src_channels:
        db.add(Channel(
            tenant_id=tenant_id, name=ch.name, channel_type=ch.channel_type,
            config_json=ch.config_json, enabled=ch.enabled,
        ))
    report["channels"] = len(src_channels)

    # 6. KPI metrics —— 按行业模板或默认指标
    kpi_metrics = ["卖卡数", "成单率", "邀约到店率", "复购率", "流失率"]
    if industry_id:
        from app.models import IndustryTemplate
        tmpl = db.query(IndustryTemplate).filter(
            IndustryTemplate.industry_id == industry_id, IndustryTemplate.kind == "kpi",
        ).first()
        if tmpl and tmpl.data_json and "metrics" in tmpl.data_json:
            kpi_metrics = tmpl.data_json["metrics"]
    from datetime import datetime
    week = datetime.now().strftime("W%V")
    for metric in kpi_metrics:
        lower = metric in ("流失率",)
        db.add(KpiMetric(
            tenant_id=tenant_id, week=week, metric=metric,
            target=0.0, actual=0.0, lower_better=lower, note=None,
        ))
    report["kpi_metrics"] = len(kpi_metrics)

    return report


@router.post("/brands")
def create_brand(
    payload: BrandCreateIn,
    db=Depends(get_db),
    _auth: dict = Depends(require_roles("admin")),
) -> dict:
    """一键派生新品牌分支：自动复制 Agent/Channel/KPI/PromptTemplate/LLMConfig/ToolRegistry，策略/护栏/知识通过 asset_resolver 继承。"""
    existing = db.query(Tenant).filter(Tenant.code == payload.code).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"品牌编码 {payload.code} 已存在")
    tenant = Tenant(
        id=str(uuid.uuid4()),
        name=payload.name,
        code=payload.code,
        industry_id=payload.industry_id,
        status="active",
        platform_version=PLATFORM_CURRENT_VERSION,
    )
    db.add(tenant)
    db.flush()

    # 一键初始化基础设施
    infra = _init_brand_infrastructure(db, tenant.id, payload.industry_id)

    # 记录审计
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        actor=_auth.get("uid", "admin"),
        action="brand.create",
        entity_type="tenant",
        entity_id=tenant.id,
        after_json={"name": payload.name, "code": payload.code, "industry_id": payload.industry_id, "infra": infra},
    ))
    db.commit()
    return {"id": tenant.id, "name": tenant.name, "code": tenant.code, "status": tenant.status, "infra": infra}


@router.get("/brands/{brand_id}")
def brand_detail(
    brand_id: str,
    db=Depends(get_db),
    _auth: dict = Depends(require_roles("admin")),
) -> dict:
    """品牌详情：完整基础设施快照（Agent/Channel/KPI/User/LLM/PromptTemplate）。"""
    tenant = db.get(Tenant, brand_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="品牌不存在")
    agents = db.query(AgentDef).filter(AgentDef.tenant_id == brand_id).all()
    channels = db.query(Channel).filter(Channel.tenant_id == brand_id).all()
    kpis = db.query(KpiMetric).filter(KpiMetric.tenant_id == brand_id).all()
    users = db.query(User).filter(User.tenant_id == brand_id).all()
    llm_configs = db.query(LLMModelConfig).filter(LLMModelConfig.tenant_id == brand_id).all()
    templates = db.query(PromptTemplate).filter(PromptTemplate.tenant_id == brand_id).all()
    # knowledge stats
    kb_docs = db.query(KnowledgeDoc).filter(KnowledgeDoc.tenant_id == brand_id).all()
    kb_chunk_count = db.query(func.count(KnowledgeChunk.id)).filter(KnowledgeChunk.tenant_id == brand_id).scalar() or 0
    kb_doc_count = len(kb_docs)
    kb_total_size = sum(d.size_bytes for d in kb_docs)
    # feishu config status
    feishu = db.query(FeishuConfig).filter(FeishuConfig.tenant_id == brand_id).first()
    feishu_configured = bool(feishu and feishu.app_id)
    feishu_enabled = bool(feishu and feishu.enabled) if feishu else False
    strategies_count = db.query(func.count(Strategy.id)).filter(Strategy.tenant_id == brand_id).scalar() or 0
    return {
        "id": tenant.id,
        "name": tenant.name,
        "code": tenant.code,
        "industry_id": tenant.industry_id,
        "status": tenant.status,
        "platform_version": tenant.platform_version,
        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
        "agents": [{"id": a.id, "key": a.key, "name": a.name, "description": a.description, "enabled": a.enabled} for a in agents],
        "channels": [{"id": c.id, "name": c.name, "channel_type": c.channel_type, "enabled": c.enabled} for c in channels],
        "kpis": [{"id": k.id, "week": k.week, "metric": k.metric, "target": k.target, "actual": k.actual, "lower_better": k.lower_better} for k in kpis],
        "users": [{"id": u.id, "username": u.username, "display_name": u.display_name, "role": u.role, "enabled": u.enabled} for u in users],
        "llm_configs": [{"id": c.id, "name": c.name, "provider": c.provider, "model": c.model, "priority": c.priority, "complexity": c.complexity, "enabled": c.enabled} for c in llm_configs],
        "prompt_templates": [{"id": t.id, "key": t.key, "version": t.version, "enabled": t.enabled} for t in templates],
        "knowledge": {"doc_count": kb_doc_count, "chunk_count": kb_chunk_count, "total_size": kb_total_size},
        "feishu": {"configured": feishu_configured, "enabled": feishu_enabled},
        "strategies_count": strategies_count,
    }


class BrandStatusIn(BaseModel):
    status: str  # active | suspended | terminated


@router.put("/brands/{brand_id}/status")
def update_brand_status(
    brand_id: str,
    payload: BrandStatusIn,
    db=Depends(get_db),
    _auth: dict = Depends(require_roles("admin")),
) -> dict:
    """启停/解约品牌。"""
    tenant = db.get(Tenant, brand_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="品牌不存在")
    if tenant.code == "default":
        raise HTTPException(status_code=400, detail="默认租户不可停用")
    old_status = tenant.status
    tenant.status = payload.status
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=brand_id,
        actor=_auth.get("uid", "admin"),
        action="brand.status_change",
        entity_type="tenant",
        entity_id=brand_id,
        before_json={"status": old_status},
        after_json={"status": payload.status},
    ))
    db.commit()
    return {"id": tenant.id, "status": tenant.status}


# ── 平台版本升级 ──────────────────────────────────────────


class VersionUpgradeIn(BaseModel):
    version: str | None = None  # 不填则自动递增


@router.post("/platform-version/upgrade")
def upgrade_platform_version(
    payload: VersionUpgradeIn,
    db=Depends(get_db),
    _auth: dict = Depends(require_roles("admin")),
) -> dict:
    """平台版本升级：将所有活跃品牌的 platform_version 统一推到新版本。"""
    new_version = payload.version or PLATFORM_CURRENT_VERSION
    active_brands = db.query(Tenant).filter(Tenant.status == "active").all()
    updated = []
    for t in active_brands:
        old = t.platform_version
        t.platform_version = new_version
        updated.append({"id": t.id, "name": t.name, "old": old, "new": new_version})
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        tenant_id="platform",
        actor=_auth.get("uid", "admin"),
        action="platform.version_upgrade",
        entity_type="platform",
        entity_id=None,
        before_json={},
        after_json={"version": new_version, "brands_updated": len(updated)},
    ))
    db.commit()
    return {"version": new_version, "brands_updated": len(updated), "details": updated}


# ── 用户管理 ──────────────────────────────────────────────


@router.get("/brands/{brand_id}/users")
def list_brand_users(
    brand_id: str,
    db=Depends(get_db),
    _auth: dict = Depends(require_roles("admin")),
) -> list[dict]:
    """列出某品牌下的所有用户。"""
    tenant = db.get(Tenant, brand_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="品牌不存在")
    users = db.query(User).filter(User.tenant_id == brand_id).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "role": u.role,
            "enabled": u.enabled,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


class UserCreateIn(BaseModel):
    username: str
    password: str
    display_name: str | None = None
    role: str = "operator"  # admin | operator | viewer


@router.post("/brands/{brand_id}/users")
def create_brand_user(
    brand_id: str,
    payload: UserCreateIn,
    db=Depends(get_db),
    _auth: dict = Depends(require_roles("admin")),
) -> dict:
    """为某品牌创建用户。"""
    tenant = db.get(Tenant, brand_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="品牌不存在")
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=409, detail=f"用户名 {payload.username} 已存在")
    if payload.role not in ("admin", "operator", "viewer"):
        raise HTTPException(status_code=400, detail="角色必须为 admin / operator / viewer")
    user = User(
        id=str(uuid.uuid4()),
        tenant_id=brand_id,
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role=payload.role,
        enabled=True,
    )
    db.add(user)
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=brand_id,
        actor=_auth.get("uid", "admin"),
        action="user.create",
        entity_type="user",
        entity_id=user.id,
        after_json={"username": payload.username, "role": payload.role},
    ))
    db.commit()
    return {"id": user.id, "username": user.username, "role": user.role, "enabled": user.enabled}


class UserUpdateIn(BaseModel):
    role: str | None = None
    enabled: bool | None = None


@router.put("/users/{user_id}")
def update_user(
    user_id: str,
    payload: UserUpdateIn,
    db=Depends(get_db),
    _auth: dict = Depends(require_roles("admin")),
) -> dict:
    """修改用户角色或启停。"""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    before = {"role": user.role, "enabled": user.enabled}
    if payload.role is not None:
        if payload.role not in ("admin", "operator", "viewer"):
            raise HTTPException(status_code=400, detail="角色必须为 admin / operator / viewer")
        user.role = payload.role
    if payload.enabled is not None:
        user.enabled = payload.enabled
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        actor=_auth.get("uid", "admin"),
        action="user.update",
        entity_type="user",
        entity_id=user.id,
        before_json=before,
        after_json={"role": user.role, "enabled": user.enabled},
    ))
    db.commit()
    return {"id": user.id, "role": user.role, "enabled": user.enabled}


# ── 计量对账 ──────────────────────────────────────────────


@router.get("/metering")
def metering_overview(
    db=Depends(get_db),
    _auth: dict = Depends(require_roles("admin")),
) -> list[dict]:
    """按品牌汇总 LLM Token 用量、API 调用量、成本。"""
    tenants = db.query(Tenant).order_by(Tenant.created_at.asc()).all()
    result = []
    for t in tenants:
        llm_stats = db.query(
            func.count(LLMCallLog.id),
            func.sum(LLMCallLog.prompt_tokens),
            func.sum(LLMCallLog.completion_tokens),
            func.sum(LLMCallLog.cost),
            func.avg(LLMCallLog.latency_ms),
        ).filter(LLMCallLog.tenant_id == t.id).one()
        api_stats = db.query(
            func.count(ApiLog.id),
        ).filter(ApiLog.tenant_id == t.id).one()
        task_stats = db.query(
            func.count(StrategyTask.id),
        ).filter(StrategyTask.tenant_id == t.id).one()
        result.append({
            "brand_id": t.id,
            "brand_name": t.name,
            "llm_calls": llm_stats[0] or 0,
            "prompt_tokens": int(llm_stats[1] or 0),
            "completion_tokens": int(llm_stats[2] or 0),
            "total_tokens": int((llm_stats[1] or 0) + (llm_stats[2] or 0)),
            "llm_cost": round(float(llm_stats[3] or 0), 4),
            "avg_latency_ms": round(float(llm_stats[4] or 0), 0),
            "api_calls": api_stats[0] or 0,
            "tasks": task_stats[0] or 0,
        })
    return result


@router.get("/metering/{brand_id}")
def metering_detail(
    brand_id: str,
    db=Depends(get_db),
    _auth: dict = Depends(require_roles("admin")),
) -> dict:
    """单个品牌的计量明细（最近 50 条 LLM 调用）。"""
    tenant = db.get(Tenant, brand_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="品牌不存在")
    logs = db.query(LLMCallLog).filter(
        LLMCallLog.tenant_id == brand_id
    ).order_by(LLMCallLog.created_at.desc()).limit(50).all()
    return {
        "brand_id": brand_id,
        "brand_name": tenant.name,
        "logs": [
            {
                "id": log.id,
                "model": log.model,
                "provider": log.provider,
                "prompt_tokens": log.prompt_tokens,
                "completion_tokens": log.completion_tokens,
                "cost": round(log.cost, 6),
                "latency_ms": log.latency_ms,
                "status": log.status,
                "error": log.error,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }


# ── 操作审计 ──────────────────────────────────────────────


@router.get("/audit")
def list_audit_logs(
    db=Depends(get_db),
    brand_id: str | None = Query(None, description="按品牌过滤"),
    action: str | None = Query(None, description="按动作类型过滤"),
    limit: int = Query(100, le=500),
    _auth: dict = Depends(require_roles("admin")),
) -> list[dict]:
    """审计日志列表，支持按品牌/动作过滤。"""
    q = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if brand_id:
        q = q.filter(AuditLog.tenant_id == brand_id)
    if action:
        q = q.filter(AuditLog.action == action)
    rows = q.all()
    return [
        {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "actor": row.actor,
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "before": row.before_json,
            "after": row.after_json,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.get("/platform-assets")
def platform_asset_overview(
    db=Depends(get_db),
    _auth: dict = Depends(require_roles("admin")),
) -> dict:
    """平台级资产总览：策略、护栏、知识的平台级数量 vs 品牌级数量。"""
    platform_strategies = db.query(Strategy).filter(
        Strategy.is_platform == True  # noqa: E712
    ).all()
    platform_guardrails = db.query(GuardrailRule).filter(
        GuardrailRule.is_platform == True  # noqa: E712
    ).all()
    platform_knowledge = db.query(KnowledgeDoc).filter(
        KnowledgeDoc.is_platform == True  # noqa: E712
    ).all() if hasattr(KnowledgeDoc, "is_platform") else []
    return {
        "strategies": {
            "platform": len(platform_strategies),
            "names": [s.name for s in platform_strategies[:20]],
        },
        "guardrails": {
            "platform": len(platform_guardrails),
            "names": [g.name for g in platform_guardrails[:20]],
        },
        "knowledge": {
            "platform": len(platform_knowledge),
        },
        "brands": db.query(Tenant).filter(Tenant.status == "active").count(),
    }
