from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_roles
from app.api.deps import Runtime, get_runtime
from app.flywheel.worker import enqueue_task
from app.models import FeedbackEvent, Instruction, Strategy, StrategyTask
from app.services.asset_resolver import resolve_assets, promote_to_platform, create_brand_override
from app.services.strategy_effect import get_effect_breakdown, get_effect_leaderboard, recalc_strategy_effect

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])


class StrategyRunIn(BaseModel):
    strategy_id: str
    conversation_id: str | None = None
    text: str | None = None


class StrategyCreateIn(BaseModel):
    title: str
    audience: str | None = None
    hook: str | None = None
    script: str | None = None
    task: str | None = None
    acceptance: str | None = None
    card_ids: list[str] = []
    activity_type: str | None = None
    channels: str | None = None
    layers: str | None = None
    sections: str | None = None
    kpi_metrics: str | None = None
    cadence: str | None = None
    cards: str | None = None


@router.get("")
def list_strategies(runtime: Runtime = Depends(get_runtime)) -> list[dict]:
    rows = resolve_assets(runtime.db, Strategy, runtime.tenant_id, runtime.industry_id)
    return [
        {
            "id": row.id,
            "name": row.name,
            "strategy_type": row.strategy_type,
            "agent_key": row.agent_key,
            "params": row.params_json,
            "status": row.status,
            "managed": row.managed,
            "enabled": row.enabled,
            "score": round(row.score or 0.0, 4),
            "runs": row.runs or 0,
            "wins": row.wins or 0,
            "feedback_count": row.feedback_count or 0,
            "last_kpi": row.last_kpi_json,
           "is_platform": row.is_platform,
           "platform_ref": row.platform_ref,
            "scenario_tags": row.scenario_tags_json or [],
            "audience_tags": row.audience_tags_json or [],
            "channel_tags": row.channel_tags_json or [],
            "is_candidate": row.is_candidate,
            "candidate_status": row.candidate_status or "",
            "parent_ids": row.parent_ids_json or [],
            "mutation_note": row.mutation_note or "",
       }
       for row in rows
   ]


@router.post("")
def create_strategy(
    payload: StrategyCreateIn,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    strategy = Strategy(
        tenant_id=runtime.tenant_id,
        industry_id=runtime.industry_id,
        name=payload.title,
        strategy_type="campaign",
        agent_key="content_writer",
        params_json={
            "audience": payload.audience,
            "hook": payload.hook,
            "script": payload.script,
            "task": payload.task,
            "acceptance": payload.acceptance,
            "card_ids": payload.card_ids,
            "activity_type": payload.activity_type,
            "channels": payload.channels,
            "layers": payload.layers,
            "sections": payload.sections,
            "kpi_metrics": payload.kpi_metrics,
            "cadence": payload.cadence,
            "cards": payload.cards,
        },
        status="草稿",
        managed=False,
        enabled=True,
    )
    runtime.db.add(strategy)
    runtime.db.commit()
    runtime.db.refresh(strategy)
    return {"id": strategy.id, "name": strategy.name}


@router.post("/from-instruction/{instruction_id}")
def create_strategy_from_instruction(
    instruction_id: str,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    instruction = runtime.db.get(Instruction, instruction_id)
    if instruction is None or instruction.tenant_id != runtime.tenant_id:
        raise HTTPException(status_code=404, detail="指令不存在")
    asset = instruction.asset_json or {}
    params = instruction.params_json or {}
    activity_plan = asset.get("activity_plan", {}) or {}
    content_schedule = asset.get("content_schedule", {}) or {}
    audience = asset.get("audience", {}) or {}
    products = asset.get("product_mix", []) or []
    scripts = asset.get("script_templates", {}) or {}
    schedules = content_schedule.get("schedules", []) or []
    strategy = Strategy(
        tenant_id=instruction.tenant_id,
        industry_id=instruction.industry_id,
        name=f"{instruction.title}·可复用打法",
        strategy_type="campaign",
        agent_key="content_writer",
        params_json={
            "activity_type": "、".join(activity_plan.get("types") or [])
            or params.get("activity_type")
            or instruction.title,
            "channels": "、".join(content_schedule.get("channels") or []) or "朋友圈,社群",
            "layers": "、".join(audience.get("layers") or []) or "潜客,新客,复购",
            "kpi_metrics": "、".join(asset.get("kpi_targets") or []) or "转化率,GMV,复购率",
            "cadence": schedules[0].get("cadence") if schedules else "每周3次",
            "cards": "、".join(str(product.get("name")) for product in products[:5]),
            "script": scripts.get("opening") or "",
            "acceptance": params.get("acceptance") or "自动验收",
        },
        status="草稿",
        managed=False,
        enabled=True,
    )
    runtime.db.add(strategy)
    runtime.db.commit()
    runtime.db.refresh(strategy)
    return {"id": strategy.id, "name": strategy.name}


@router.post("/run")
def run_strategy(
    payload: StrategyRunIn,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    strategy = runtime.db.get(Strategy, payload.strategy_id)
    if strategy is None or strategy.tenant_id != runtime.tenant_id:
        raise HTTPException(status_code=404, detail="策略不存在")
    text = payload.text or (strategy.params_json or {}).get("trigger_text", "请基于当前客户情况执行策略")
    return runtime.engine.run(
        runtime.tenant_id,
        strategy.agent_key,
        conversation_id=payload.conversation_id,
        input_data={"text": text},
    )


@router.get("/tasks")
def list_strategy_tasks(runtime: Runtime = Depends(get_runtime)) -> list[dict]:
    rows = (
        runtime.db.query(StrategyTask)
        .filter(StrategyTask.tenant_id == runtime.tenant_id)
        .filter(StrategyTask.industry_id == runtime.industry_id)
        .order_by(StrategyTask.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": row.id,
            "strategy_id": row.strategy_id,
            "title": row.title,
            "channel": row.channel,
            "audience": row.audience,
            "acceptance": row.acceptance,
            "status": row.status,
            "due_at": row.due_at,
        }
        for row in rows
    ]


@router.post("/{strategy_id}/dispatch")
def dispatch_strategy(
    strategy_id: str,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    strategy = runtime.db.get(Strategy, strategy_id)
    if strategy is None or strategy.tenant_id != runtime.tenant_id:
        raise HTTPException(status_code=404, detail="策略不存在")
    params = strategy.params_json or {}
    task = StrategyTask(
        tenant_id=runtime.tenant_id,
        industry_id=strategy.industry_id,
        strategy_id=strategy.id,
        title=strategy.name,
        channel="企微",
        audience=params.get("audience"),
        script=params.get("script"),
        acceptance=params.get("acceptance"),
        status="待执行",
    )
    runtime.db.add(task)
    runtime.db.commit()
    runtime.db.refresh(task)
    enqueue_task(task.id)
    return {"id": task.id, "status": task.status}


@router.post("/{strategy_id}/toggle-managed")
def toggle_managed(
    strategy_id: str,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    strategy = runtime.db.get(Strategy, strategy_id)
    if strategy is None or strategy.tenant_id != runtime.tenant_id:
        raise HTTPException(status_code=404, detail="策略不存在")
    strategy.managed = not strategy.managed
    strategy.status = "托管" if strategy.managed else "草稿"
    runtime.db.commit()
    return {"id": strategy.id, "managed": strategy.managed, "status": strategy.status}


@router.get("/effects")
def strategy_effects(runtime: Runtime = Depends(get_runtime)) -> list[dict]:
    """策略效果排行榜，按 score 降序。"""
    return get_effect_leaderboard(runtime.db, runtime.tenant_id, runtime.industry_id, limit=50)


@router.post("/recalc-effects")
def recalc_all_effects(
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    """全量重算所有策略的效果分。"""
    rows = (
        runtime.db.query(Strategy)
        .filter(Strategy.tenant_id == runtime.tenant_id)
        .all()
    )
    count = 0
    for row in rows:
        recalc_strategy_effect(runtime.db, row.id)
        count += 1
    return {"recalculated": count}


class PromoteIn(BaseModel):
    strategy_id: str


@router.post("/promote-platform")
def promote_strategy_to_platform(
    payload: PromoteIn,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin")),
) -> dict:
    """把品牌级策略提升为平台级，所有品牌继承。"""
    s = promote_to_platform(runtime.db, Strategy, payload.strategy_id)
    if s is None:
        raise HTTPException(status_code=404, detail="策略不存在或已是平台级")
    return {"id": s.id, "is_platform": s.is_platform}


class OverrideIn(BaseModel):
    platform_strategy_id: str
    name: str | None = None
    params: dict | None = None


@router.post("/brand-override")
def create_strategy_override(
    payload: OverrideIn,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    """基于平台策略创建品牌级覆盖副本。"""
    overrides = {}
    if payload.name:
        overrides["name"] = payload.name
    if payload.params:
        overrides["params_json"] = payload.params
    s = create_brand_override(runtime.db, Strategy, payload.platform_strategy_id, runtime.tenant_id, overrides)
    if s is None:
        raise HTTPException(status_code=404, detail="平台策略不存在")
    return {"id": s.id, "name": s.name, "platform_ref": s.platform_ref}


# ── 效果回流：反馈事件 & 效果分解 ──────────────────────────


@router.get("/{strategy_id}/feedback")
def strategy_feedback(
    strategy_id: str,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> list[dict]:
    """列出某条策略关联的飞书反馈事件。"""
    rows = (
        runtime.db.query(FeedbackEvent)
        .filter(FeedbackEvent.strategy_id == strategy_id)
        .order_by(FeedbackEvent.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": row.id,
            "action": row.action,
            "amount": row.amount,
            "note": row.note,
            "occurred_at": row.occurred_at,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.get("/{strategy_id}/effect-breakdown")
def strategy_effect_breakdown(
    strategy_id: str,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    """策略效果分三组成分明细。"""
    return get_effect_breakdown(runtime.db, strategy_id)


@router.get("/feedback-events/recent")
def recent_feedback_events(
    runtime: Runtime = Depends(get_runtime),
    limit: int = 50,
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> list[dict]:
    """最近反馈事件流（含策略名称）。"""
    rows = (
        runtime.db.query(FeedbackEvent)
        .filter(FeedbackEvent.tenant_id == runtime.tenant_id)
        .order_by(FeedbackEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    result = []
    for row in rows:
        strategy_name = ""
        if row.strategy_id:
            s = runtime.db.get(Strategy, row.strategy_id)
            strategy_name = s.name if s else ""
        result.append({
            "id": row.id,
            "action": row.action,
            "amount": row.amount,
            "note": (row.note or "")[:120],
            "strategy_id": row.strategy_id,
            "strategy_name": strategy_name,
            "occurred_at": row.occurred_at,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })
    return result


# ── P2-2: 跨行業策略復用 + AI 變異組合 ──────────────────────


class TagUpdateIn(BaseModel):
    scenario_tags: list[str] | None = None
    audience_tags: list[str] | None = None
    channel_tags: list[str] | None = None


@router.put("/{strategy_id}/tags")
def update_strategy_tags(
    strategy_id: str,
    payload: TagUpdateIn,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    """更新策略卡的場景/人群/渠道標籤。"""
    s = runtime.db.get(Strategy, strategy_id)
    if s is None or s.tenant_id != runtime.tenant_id:
        raise HTTPException(status_code=404, detail="策略不存在")
    if payload.scenario_tags is not None:
        s.scenario_tags_json = payload.scenario_tags
    if payload.audience_tags is not None:
        s.audience_tags_json = payload.audience_tags
    if payload.channel_tags is not None:
        s.channel_tags_json = payload.channel_tags
    runtime.db.commit()
    return {"id": s.id, "scenario_tags": s.scenario_tags_json, "audience_tags": s.audience_tags_json, "channel_tags": s.channel_tags_json}


def _tag_overlap(a: list, b: list) -> int:
    if not a or not b:
        return 0
    return len(set(a) & set(b))


@router.get("/recommend")
def recommend_strategies(
    runtime: Runtime = Depends(get_runtime),
    scenario: str | None = None,
    audience: str | None = None,
    channel: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """跨行業策略推薦：按標籤相似度 + 效果分排序，返回其他行業驗證過的打法。"""
    q = (
        runtime.db.query(Strategy)
        .filter(Strategy.tenant_id == runtime.tenant_id)
        .filter(Strategy.is_candidate == False)
    )
    if runtime.industry_id:
        q = q.filter(Strategy.industry_id != runtime.industry_id)
    rows = q.all()
    results = []
    for s in rows:
        scenario_tags = (s.scenario_tags_json or [])
        audience_tags = (s.audience_tags_json or [])
        channel_tags = (s.channel_tags_json or [])
        sim = 0
        if scenario:
            sim += _tag_overlap(scenario_tags, [scenario]) * 3
        if audience:
            sim += _tag_overlap(audience_tags, [audience]) * 2
        if channel:
            sim += _tag_overlap(channel_tags, [channel]) * 1
        # 效果分加權
        total = sim + (s.score or 0) * 5
        if total > 0 or sim > 0:
            results.append({
                "id": s.id,
                "name": s.name,
                "strategy_type": s.strategy_type,
                "score": round(s.score or 0.0, 4),
                "runs": s.runs or 0,
                "wins": s.wins or 0,
                "industry_id": s.industry_id,
                "scenario_tags": scenario_tags,
                "audience_tags": audience_tags,
                "channel_tags": channel_tags,
                "similarity": sim,
                "params": s.params_json,
            })
    results.sort(key=lambda x: x["similarity"] + x["score"] * 5, reverse=True)
    return results[:limit]


class MutateIn(BaseModel):
    strategy_ids: list[str]
    note: str | None = None


@router.post("/mutate")
def mutate_strategies(
    payload: MutateIn,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    """AI 變異組合：取 2+ 已驗證策略，合成候選新策略，等待人工審核。"""
    if len(payload.strategy_ids) < 2:
        raise HTTPException(status_code=400, detail="至少選擇 2 個策略進行組合")
    parents = (
        runtime.db.query(Strategy)
        .filter(Strategy.id.in_(payload.strategy_ids))
        .filter(Strategy.tenant_id == runtime.tenant_id)
        .all()
    )
    if len(parents) < 2:
        raise HTTPException(status_code=404, detail="找不到足夠的策略")
    # 合併 params
    merged_params: dict = {}
    all_scenarios: list[str] = []
    all_audiences: list[str] = []
    all_channels: list[str] = []
    parent_names: list[str] = []
    for p in parents:
        parent_names.append(p.name)
        for k, v in (p.params_json or {}).items():
            if k not in merged_params and v:
                merged_params[k] = v
        all_scenarios.extend(p.scenario_tags_json or [])
        all_audiences.extend(p.audience_tags_json or [])
        all_channels.extend(p.channel_tags_json or [])
    # 去重
    all_scenarios = list(dict.fromkeys(all_scenarios))
    all_audiences = list(dict.fromkeys(all_audiences))
    all_channels = list(dict.fromkeys(all_channels))
    note = payload.note or f"由 {' + '.join(parent_names[:3])} 組合生成"
    candidate = Strategy(
        tenant_id=runtime.tenant_id,
        industry_id=runtime.industry_id,
        name=f"[候選] {parent_names[0]} × {parent_names[1]}" if len(parent_names) >= 2 else "[候選] 組合策略",
        strategy_type="campaign",
        agent_key="content_writer",
        params_json=merged_params,
        status="候選",
        managed=False,
        enabled=False,
        is_candidate=True,
        candidate_status="pending",
        parent_ids_json=payload.strategy_ids,
        mutation_note=note,
        scenario_tags_json=all_scenarios,
        audience_tags_json=all_audiences,
        channel_tags_json=all_channels,
    )
    runtime.db.add(candidate)
    runtime.db.commit()
    runtime.db.refresh(candidate)
    return {"id": candidate.id, "name": candidate.name, "note": note}


@router.get("/candidates")
def list_candidates(runtime: Runtime = Depends(get_runtime)) -> list[dict]:
    """列出 AI 生成的候選策略（待審核）。"""
    rows = (
        runtime.db.query(Strategy)
        .filter(Strategy.tenant_id == runtime.tenant_id)
        .filter(Strategy.is_candidate == True)
        .order_by(Strategy.created_at.desc())
        .limit(50)
        .all()
    )
    results = []
    for s in rows:
        parent_names: list[str] = []
        if s.parent_ids_json:
            parents = runtime.db.query(Strategy).filter(Strategy.id.in_(s.parent_ids_json)).all()
            parent_names = [p.name for p in parents]
        results.append({
            "id": s.id,
            "name": s.name,
            "candidate_status": s.candidate_status or "pending",
            "mutation_note": s.mutation_note,
            "parent_names": parent_names,
            "scenario_tags": s.scenario_tags_json or [],
            "audience_tags": s.audience_tags_json or [],
            "channel_tags": s.channel_tags_json or [],
            "params": s.params_json,
            "score": round(s.score or 0.0, 4),
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    return results


@router.post("/candidates/{strategy_id}/approve")
def approve_candidate(
    strategy_id: str,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    """審核通過：候選策略轉正進入策略庫。"""
    s = runtime.db.get(Strategy, strategy_id)
    if s is None or s.tenant_id != runtime.tenant_id:
        raise HTTPException(status_code=404, detail="策略不存在")
    if not s.is_candidate:
        raise HTTPException(status_code=400, detail="不是候選策略")
    s.is_candidate = False
    s.candidate_status = "approved"
    s.status = "草稿"
    s.enabled = True
    # 去掉名稱前綴
    if s.name.startswith("[候選] "):
        s.name = s.name[5:]
    runtime.db.commit()
    return {"id": s.id, "name": s.name, "status": "approved"}


@router.post("/candidates/{strategy_id}/reject")
def reject_candidate(
    strategy_id: str,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    """審核拒絕：候選策略標記為 rejected。"""
    s = runtime.db.get(Strategy, strategy_id)
    if s is None or s.tenant_id != runtime.tenant_id:
        raise HTTPException(status_code=404, detail="策略不存在")
    if not s.is_candidate:
        raise HTTPException(status_code=400, detail="不是候選策略")
    s.candidate_status = "rejected"
    s.enabled = False
    runtime.db.commit()
    return {"id": s.id, "status": "rejected"}
