from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func

from app.api.deps import Runtime, get_runtime
from app.auth import require_roles
from app.channels.gateway import channel_gateway
from app.models import (
    AgentDef,
    Channel,
    Conversation,
    DemandSignal,
    FlywheelMetric,
    GuardrailHit,
    GuardrailRule,
    LLMBudget,
    LLMCallLog,
    LLMModelConfig,
    Message,
    StrategyExecution,
)
from app.models import new_id

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class ChannelUpdateIn(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    config: dict | None = None


@router.get("/overview")
def admin_overview(runtime: Runtime = Depends(get_runtime)) -> dict:
    tenant = runtime.tenant_id
    counts = {
        "conversations": runtime.db.query(Conversation).filter(Conversation.tenant_id == tenant).count(),
        "messages": runtime.db.query(Message).filter(Message.tenant_id == tenant).count(),
        "signals": runtime.db.query(DemandSignal).filter(DemandSignal.tenant_id == tenant).count(),
        "flywheel_cycles": runtime.db.query(StrategyExecution).filter(StrategyExecution.tenant_id == tenant).count(),
        "guardrail_hits": runtime.db.query(GuardrailHit).filter(GuardrailHit.tenant_id == tenant).count(),
        "llm_calls": runtime.db.query(LLMCallLog).filter(LLMCallLog.tenant_id == tenant).count(),
    }
    recent = (
        runtime.db.query(Conversation)
        .filter(Conversation.tenant_id == tenant)
        .order_by(Conversation.created_at.desc())
        .limit(8)
        .all()
    )
    metric = (
        runtime.db.query(
            func.count(FlywheelMetric.id),
            func.avg(FlywheelMetric.closed_loop_days),
            func.sum(FlywheelMetric.hit_count),
            func.sum(FlywheelMetric.adopted_count),
            func.avg(FlywheelMetric.roi),
        )
        .filter(FlywheelMetric.tenant_id == tenant)
        .one()
    )
    return {
        **counts,
        "flywheel": {
            "total_cycles": metric[0] or 0,
            "avg_closed_loop_days": round(metric[1] or 0, 2),
            "total_hit_count": metric[2] or 0,
            "total_adopted_count": metric[3] or 0,
            "avg_roi": round(metric[4] or 0, 2),
        },
        "recent_conversations": [
            {
                "id": row.id,
                "title": row.title,
                "status": row.status,
                "conversation_type": row.conversation_type,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in recent
        ],
    }


@router.get("/channels")
def list_channels(runtime: Runtime = Depends(get_runtime)) -> list[dict]:
    rows = (
        runtime.db.query(Channel)
        .filter(Channel.tenant_id == runtime.tenant_id)
        .order_by(Channel.created_at.asc())
        .all()
    )
    return [
        {
            "id": row.id,
            "name": row.name,
            "channel_type": row.channel_type,
            "enabled": row.enabled,
            "config": row.config_json,
        }
        for row in rows
    ]


@router.put("/channels/{channel_id}")
def update_channel(
    channel_id: str,
    payload: ChannelUpdateIn,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin")),
) -> dict:
    channel = runtime.db.get(Channel, channel_id)
    if channel is None or channel.tenant_id != runtime.tenant_id:
        raise HTTPException(status_code=404, detail="渠道不存在")
    if payload.name is not None:
        channel.name = payload.name
    if payload.enabled is not None:
        channel.enabled = payload.enabled
    if payload.config is not None:
        channel.config_json = payload.config
    runtime.db.commit()
    return {
        "id": channel.id,
        "name": channel.name,
        "channel_type": channel.channel_type,
        "enabled": channel.enabled,
        "config": channel.config_json,
    }


@router.post("/channels/{channel_id}/test")
def test_channel(
    channel_id: str,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    channel = runtime.db.get(Channel, channel_id)
    if channel is None or channel.tenant_id != runtime.tenant_id:
        raise HTTPException(status_code=404, detail="渠道不存在")
    result = channel_gateway.send(
        channel.channel_type,
        channel.id,
        channel.id,
        "这是一条渠道连通性测试消息",
        channel.config_json or {},
    )
    return {"ok": result.ok, "message_id": result.message_id, "detail": result.detail}


@router.get("/agents")
def list_admin_agents(runtime: Runtime = Depends(get_runtime)) -> list[dict]:
    rows = (
        runtime.db.query(AgentDef)
        .filter(AgentDef.tenant_id == runtime.tenant_id)
        .order_by(AgentDef.created_at.asc())
        .all()
    )
    return [
        {"key": row.key, "name": row.name, "description": row.description, "enabled": row.enabled}
        for row in rows
    ]


@router.get("/guardrails/rules")
def list_guardrail_rules(runtime: Runtime = Depends(get_runtime)) -> list[dict]:
    rows = (
        runtime.db.query(GuardrailRule)
        .filter(GuardrailRule.tenant_id == runtime.tenant_id)
        .order_by(GuardrailRule.created_at.asc())
        .all()
    )
    return [
        {
            "id": row.id,
            "name": row.name,
            "rule_type": row.rule_type,
            "action": row.action,
            "pattern": row.pattern_json.get("keywords", []),
            "enabled": row.enabled,
        }
        for row in rows
    ]


@router.get("/guardrails/hits")
def list_guardrail_hits(runtime: Runtime = Depends(get_runtime)) -> list[dict]:
    rows = (
        runtime.db.query(GuardrailHit)
        .filter(GuardrailHit.tenant_id == runtime.tenant_id)
        .order_by(GuardrailHit.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": row.id,
            "content": row.content,
            "action": row.action,
            "note": row.note,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.get("/llm/models")
def list_llm_models(runtime: Runtime = Depends(get_runtime)) -> list[dict]:
    rows = (
        runtime.db.query(LLMModelConfig)
        .filter(LLMModelConfig.tenant_id == runtime.tenant_id)
        .order_by(LLMModelConfig.priority.asc())
        .all()
    )
    return [
        {
            "id": row.id,
            "name": row.name,
            "provider": row.provider,
            "model": row.model,
            "base_url": row.base_url,
            "priority": row.priority,
            "complexity": row.complexity,
            "cost_per_million": row.cost_per_million,
            "enabled": row.enabled,
           "has_key": bool(row.api_key),
       }
       for row in rows
   ]


LLM_PRESETS = [
    {
        "name": "GLM-5.2 (容联云路由)",
        "provider": "zhipu",
        "model": "glm-5.2",
        "base_url": "https://ytx-router.7moor.com/v1",
        "complexity": "complex",
        "cost_per_million": 0.0,
        "description": "免费，通过容联云路由调用，适合策略生成和内容创作",
    },
    {
        "name": "DeepSeek V3",
        "provider": "deepseek",
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "complexity": "complex",
        "cost_per_million": 2.0,
        "description": "性价比高，适合策略生成和话术创作",
    },
    {
        "name": "DeepSeek V4 Pro (阿里云百炼)",
        "provider": "deepseek",
        "model": "deepseek-v4-pro-0813",
        "base_url": "",
        "complexity": "complex",
        "cost_per_million": 2.0,
        "description": "阿里云百炼部署，需填写专属 base_url 和 api_key",
    },
    {
        "name": "Qwen 2.5 (本地 Ollama)",
        "provider": "ollama",
        "model": "qwen2.5:7b",
        "base_url": "http://localhost:11434/v1",
        "complexity": "simple",
        "cost_per_million": 0.0,
        "description": "免费本地部署，适合简单任务和测试",
    },
    {
        "name": "GPT-4o",
        "provider": "openai",
        "model": "gpt-4o",
        "base_url": "https://api.openai.com/v1",
        "complexity": "complex",
        "cost_per_million": 17.5,
        "description": "效果最好，成本较高，适合高精度任务",
    },
    {
        "name": "nomic-embed-text (本地向量)",
        "provider": "ollama",
        "model": "nomic-embed-text",
        "base_url": "http://localhost:11434/v1",
        "complexity": "embedding",
        "cost_per_million": 0.0,
        "description": "免费本地向量模型，用于知识库检索",
    },
]


class LLMModelIn(BaseModel):
    name: str
    provider: str
    model: str
    base_url: str
    api_key: str = ""
    priority: int = 1
    complexity: str = "complex"
    cost_per_million: float = 0.0
    enabled: bool = True


@router.get("/llm/presets")
def list_llm_presets() -> list[dict]:
    return LLM_PRESETS


@router.post("/llm/models")
def create_llm_model(payload: LLMModelIn, runtime: Runtime = Depends(get_runtime)) -> dict:
    row = LLMModelConfig(
        id=new_id(),
        tenant_id=runtime.tenant_id,
        name=payload.name,
        provider=payload.provider,
        model=payload.model,
        base_url=payload.base_url,
        api_key=payload.api_key,
        priority=payload.priority,
        complexity=payload.complexity,
        cost_per_million=payload.cost_per_million,
        enabled=payload.enabled,
    )
    runtime.db.add(row)
    runtime.db.commit()
    return {"id": row.id, "name": row.name, "created": True}


@router.put("/llm/models/{model_id}")
def update_llm_model(model_id: str, payload: LLMModelIn, runtime: Runtime = Depends(get_runtime)) -> dict:
    row = (
        runtime.db.query(LLMModelConfig)
        .filter(LLMModelConfig.id == model_id, LLMModelConfig.tenant_id == runtime.tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(404, "模型不存在")
    row.name = payload.name
    row.provider = payload.provider
    row.model = payload.model
    row.base_url = payload.base_url
    if payload.api_key:
        row.api_key = payload.api_key
    row.priority = payload.priority
    row.complexity = payload.complexity
    row.cost_per_million = payload.cost_per_million
    row.enabled = payload.enabled
    runtime.db.commit()
    return {"id": row.id, "updated": True}


@router.delete("/llm/models/{model_id}")
def delete_llm_model(model_id: str, runtime: Runtime = Depends(get_runtime)) -> dict:
    row = (
        runtime.db.query(LLMModelConfig)
        .filter(LLMModelConfig.id == model_id, LLMModelConfig.tenant_id == runtime.tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(404, "模型不存在")
    runtime.db.delete(row)
    runtime.db.commit()
    return {"id": model_id, "deleted": True}


@router.get("/llm/usage")
def list_llm_usage(runtime: Runtime = Depends(get_runtime)) -> dict:
    budgets = (
        runtime.db.query(LLMBudget)
        .filter(LLMBudget.tenant_id == runtime.tenant_id)
        .order_by(LLMBudget.created_at.desc())
        .limit(10)
        .all()
    )
    logs = (
        runtime.db.query(LLMCallLog)
        .filter(LLMCallLog.tenant_id == runtime.tenant_id)
        .order_by(LLMCallLog.created_at.desc())
        .limit(20)
        .all()
    )
    return {
        "budgets": [
            {
                "id": row.id,
                "period_type": row.period_type,
                "period_key": row.period_key,
                "token_limit": row.token_limit,
                "tokens_used": row.tokens_used,
                "cost_limit": row.cost_limit,
                "cost_used": row.cost_used,
            }
            for row in budgets
        ],
        "logs": [
            {
                "id": row.id,
                "model": row.model,
                "provider": row.provider,
                "prompt_tokens": row.prompt_tokens,
                "completion_tokens": row.completion_tokens,
                "latency_ms": row.latency_ms,
                "cost": row.cost,
                "status": row.status,
                "error": row.error,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in logs
        ],
    }
