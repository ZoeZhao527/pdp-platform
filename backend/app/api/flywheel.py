from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func

from app.auth import require_roles
from app.api.deps import Runtime, get_runtime
from app.config import get_settings
from app.flywheel.automation import FlywheelAutomation, last_run_state
from app.flywheel.stages import score_match_profile, structure_signal
from app.flywheel.worker import enqueue_signal
from app.models import (
    Capability,
    DemandProfile,
    DemandSignal,
    FlywheelMetric,
    MatchResult,
    Strategy,
    StrategyExecution,
)
from app.schemas import FlywheelTriggerIn

router = APIRouter(prefix="/api/v1/flywheel", tags=["flywheel"])


class SignalCreate(BaseModel):
    raw_text: str
    source_type: str = "manual"


class SignalBatchCreate(BaseModel):
    items: list[str]


class ProductIn(BaseModel):
    name: str
    category: str | None = None
    price: int = 0
    price_band: str | None = None
    efficacy: list[str] = []
    segments: list[str] = []
    seasons: list[str] = []
    description: str | None = None
    is_focus: bool = False


class ProductImportIn(BaseModel):
    items: list[ProductIn]


@router.get("/signals")
def list_signals(
    status: str | None = None,
    source_type: str | None = None,
    limit: int = 50,
    runtime: Runtime = Depends(get_runtime),
) -> list[dict]:
    query = runtime.db.query(DemandSignal).filter(DemandSignal.tenant_id == runtime.tenant_id)
    query = query.filter(DemandSignal.industry_id == runtime.industry_id)
    if status:
        query = query.filter(DemandSignal.status == status)
    if source_type:
        query = query.filter(DemandSignal.source_type == source_type)
    rows = query.order_by(DemandSignal.created_at.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "source_type": row.source_type,
            "raw_content": row.raw_content,
            "status": row.status,
            "customer_id": row.customer_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.post("/signals")
def create_signal(
    payload: SignalCreate,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    signal = DemandSignal(
        tenant_id=runtime.tenant_id,
        industry_id=runtime.industry_id,
        source_type=payload.source_type,
        raw_content=payload.raw_text,
    )
    runtime.db.add(signal)
    runtime.db.commit()
    runtime.db.refresh(signal)
    enqueue_signal(signal.id)
    return {"id": signal.id, "status": signal.status}


@router.post("/signals/batch")
def create_signals_batch(
    payload: SignalBatchCreate,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    added = 0
    added_ids: list[str] = []
    for text in payload.items:
        text = text.strip()
        if not text:
            continue
        signal = DemandSignal(
            tenant_id=runtime.tenant_id,
            industry_id=runtime.industry_id,
            source_type="manual",
            raw_content=text,
        )
        runtime.db.add(signal)
        runtime.db.flush()
        added_ids.append(signal.id)
        added += 1
    runtime.db.commit()
    for signal_id in added_ids:
        enqueue_signal(signal_id)
    return {"added": added}


@router.post("/signals/{signal_id}/label")
def label_signal(
    signal_id: str,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    signal = runtime.db.get(DemandSignal, signal_id)
    if signal is None or signal.tenant_id != runtime.tenant_id:
        raise HTTPException(status_code=404, detail="信号不存在")
    profile = structure_signal(runtime.db, signal)
    signal.status = "labeled"
    runtime.db.commit()
    return {
        "id": signal.id,
        "status": signal.status,
        "scenario": profile.scenario,
        "tags": profile.tags_json,
    }


@router.post("/demands/{demand_id}/verify")
def verify_demand(
    demand_id: str,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    profile = runtime.db.get(DemandProfile, demand_id)
    if profile is None or profile.tenant_id != runtime.tenant_id:
        raise HTTPException(status_code=404, detail="需求不存在")
    profile.verified = True
    runtime.db.commit()
    return {"id": profile.id, "verified": True}


@router.get("/demands")
def list_demands(limit: int = 50, runtime: Runtime = Depends(get_runtime)) -> list[dict]:
    rows = (
        runtime.db.query(DemandProfile)
        .filter(DemandProfile.tenant_id == runtime.tenant_id)
        .filter(DemandProfile.industry_id == runtime.industry_id)
        .order_by(DemandProfile.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": row.id,
            "signal_id": row.signal_id,
            "scenario": row.scenario,
            "tags": row.tags_json if isinstance(row.tags_json, list) else (row.tags_json or {}).get("tags", []),
            "intensity": row.intensity,
            "verified": row.verified,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.get("/products")
def list_products(runtime: Runtime = Depends(get_runtime)) -> list[dict]:
    rows = (
        runtime.db.query(Capability)
        .filter(Capability.tenant_id == runtime.tenant_id)
        .filter(Capability.industry_id == runtime.industry_id)
        .order_by(Capability.category.asc(), Capability.is_focus.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "name": row.product,
            "category": row.category,
            "price": row.price,
            "price_band": row.price_band,
            "efficacy": row.efficacy_json or [],
            "segments": row.segments_json or [],
            "seasons": row.seasons_json or [],
            "description": row.description,
            "is_focus": row.is_focus,
        }
        for row in rows
    ]


@router.post("/products")
def create_product(
    payload: ProductIn,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    capability = Capability(
        tenant_id=runtime.tenant_id,
        industry_id=runtime.industry_id,
        category=payload.category,
        industry="多行业",
        product=payload.name,
        capability=payload.name,
        price=payload.price,
        price_band=payload.price_band,
        efficacy_json=payload.efficacy,
        segments_json=payload.segments,
        seasons_json=payload.seasons,
        description=payload.description,
        is_focus=payload.is_focus,
        match_rules_json={"keywords": payload.efficacy},
    )
    runtime.db.add(capability)
    runtime.db.commit()
    runtime.db.refresh(capability)
    return {"id": capability.id, "name": capability.product}


@router.put("/products/{product_id}")
def update_product(
    product_id: str,
    payload: ProductIn,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    capability = runtime.db.get(Capability, product_id)
    if capability is None or capability.tenant_id != runtime.tenant_id:
        raise HTTPException(status_code=404, detail="品项不存在")
    capability.product = payload.name
    capability.category = payload.category
    capability.price = payload.price
    capability.price_band = payload.price_band
    capability.efficacy_json = payload.efficacy
    capability.segments_json = payload.segments
    capability.seasons_json = payload.seasons
    capability.description = payload.description
    capability.is_focus = payload.is_focus
    capability.match_rules_json = {"keywords": payload.efficacy}
    runtime.db.commit()
    return {"id": capability.id, "name": capability.product}


@router.delete("/products/{product_id}")
def delete_product(
    product_id: str,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    capability = runtime.db.get(Capability, product_id)
    if capability is None or capability.tenant_id != runtime.tenant_id:
        raise HTTPException(status_code=404, detail="品项不存在")
    runtime.db.delete(capability)
    runtime.db.commit()
    return {"ok": True}


@router.post("/products/import")
def import_products(
    payload: ProductImportIn,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    added = 0
    for item in payload.items:
        runtime.db.add(
            Capability(
                tenant_id=runtime.tenant_id,
                industry_id=runtime.industry_id,
                category=item.category,
                industry="多行业",
                product=item.name,
                capability=item.name,
                price=item.price,
                price_band=item.price_band,
                efficacy_json=item.efficacy,
                segments_json=item.segments,
                seasons_json=item.seasons,
                description=item.description,
                is_focus=item.is_focus,
                match_rules_json={"keywords": item.efficacy},
            )
        )
        added += 1
    runtime.db.commit()
    return {"added": added}


@router.get("/products/categories")
def list_product_categories(runtime: Runtime = Depends(get_runtime)) -> list[dict]:
    rows = (
        runtime.db.query(Capability.category, func.count(Capability.id))
        .filter(Capability.tenant_id == runtime.tenant_id)
        .filter(Capability.industry_id == runtime.industry_id)
        .group_by(Capability.category)
        .all()
    )
    return [{"category": category or "未分类", "count": count} for category, count in rows]


@router.get("/matches")
def list_matches(limit: int = 80, runtime: Runtime = Depends(get_runtime)) -> list[dict]:
    rows = (
        runtime.db.query(MatchResult)
        .filter(MatchResult.tenant_id == runtime.tenant_id)
        .filter(MatchResult.industry_id == runtime.industry_id)
        .order_by(MatchResult.score.desc())
        .limit(limit)
        .all()
    )
    results = []
    for row in rows:
        profile = runtime.db.get(DemandProfile, row.demand_id)
        capability = runtime.db.get(Capability, row.product_id)
        results.append(
            {
                "id": row.id,
                "demand_scenario": profile.scenario if profile else "-",
                "demand_tags": (
                    profile.tags_json
                    if profile and isinstance(profile.tags_json, list)
                    else ((profile.tags_json or {}).get("tags", []) if profile else [])
                ),
                "product_name": capability.product if capability else "-",
                "product_category": capability.category if capability else None,
                "score": row.score,
                "reasons": row.reasons_json or [],
            }
        )
    return results


@router.get("/advisories")
def flywheel_advisories(runtime: Runtime = Depends(get_runtime)) -> dict:
    tenant = runtime.tenant_id
    industry = runtime.industry_id
    signals = (
        runtime.db.query(DemandSignal)
        .filter(
            DemandSignal.tenant_id == tenant,
            DemandSignal.industry_id == industry,
            DemandSignal.source_type != "instruction",
        )
        .order_by(DemandSignal.created_at.desc())
        .limit(8)
        .all()
    )
    signal_rows = [
        {
            "id": row.id,
            "source_type": row.source_type,
            "raw_content": row.raw_content,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in signals
    ]

    profiles = (
        runtime.db.query(DemandProfile)
        .filter(
            DemandProfile.tenant_id == tenant,
            DemandProfile.industry_id == industry,
        )
        .order_by(DemandProfile.created_at.desc())
        .limit(100)
        .all()
    )
    demand_map: dict[str, dict] = {}
    for profile in profiles:
        scenario = profile.scenario or "待分类"
        tags = (
            profile.tags_json
            if isinstance(profile.tags_json, list)
            else (profile.tags_json or {}).get("tags", [])
        )
        item = demand_map.setdefault(
            scenario,
            {"scenario": scenario, "tags": [], "count": 0, "intensity": 0, "evidence": ""},
        )
        item["count"] += 1
        item["intensity"] = max(item["intensity"], profile.intensity)
        for tag in tags:
            if tag not in item["tags"]:
                item["tags"].append(tag)
        if not item["evidence"] and profile.evidence:
            item["evidence"] = profile.evidence
    demands = sorted(demand_map.values(), key=lambda item: item["count"], reverse=True)[:6]

    matches = (
        runtime.db.query(MatchResult)
        .filter(
            MatchResult.tenant_id == tenant,
            MatchResult.industry_id == industry,
        )
        .order_by(MatchResult.score.desc())
        .limit(6)
        .all()
    )
    match_rows = []
    for row in matches:
        profile = runtime.db.get(DemandProfile, row.demand_id)
        capability = runtime.db.get(Capability, row.product_id)
        tags = (
            profile.tags_json
            if profile and isinstance(profile.tags_json, list)
            else ((profile.tags_json or {}).get("tags", []) if profile else [])
        )
        match_rows.append(
            {
                "demand_scenario": profile.scenario if profile else "-",
                "demand_tags": tags,
                "product_name": capability.product if capability else "-",
                "product_category": capability.category if capability else None,
                "score": row.score,
                "reasons": row.reasons_json or [],
            }
        )

    strategies = (
        runtime.db.query(Strategy)
        .filter(
            Strategy.tenant_id == tenant,
            Strategy.industry_id == industry,
        )
        .order_by(Strategy.score.desc(), Strategy.created_at.desc())
        .limit(6)
        .all()
    )
    strategy_rows = [
        {
            "id": row.id,
            "name": row.name,
            "strategy_type": row.strategy_type,
            "status": row.status,
            "managed": row.managed,
            "next_run_at": row.next_run_at,
            "score": round(row.score or 0.0, 4),
            "runs": row.runs or 0,
            "wins": row.wins or 0,
            "feedback_count": row.feedback_count or 0,
        }
        for row in strategies
    ]

    suggestions: list[dict] = []
    for row in strategies:
        params = row.params_json or {}
        suggestions.append(
            {
                "id": row.id,
                "kind": "strategy",
                "title": f"策略建议：{row.name}",
                "summary": f"{row.strategy_type} · {row.status} · 效果分 {round(row.score or 0.0, 2)}（{row.runs or 0}次/胜{row.wins or 0}/反馈{row.feedback_count or 0}）",
                "params": {
                    "activity_type": params.get("activity_type") or row.name,
                    "layers": params.get("layers") or "",
                    "product_categories": params.get("cards") or "",
                    "kpi_metrics": params.get("kpi_metrics") or "",
                    "related_signals": row.name,
                },
            }
        )
    for item in demands:
        suggestions.append(
            {
                "id": f"demand-{item['scenario']}",
                "kind": "demand",
                "title": f"{item['scenario']}（{item['count']} 个需求）",
                "summary": item["evidence"] or "、".join(item["tags"]),
                "params": {
                    "layers": "、".join(item["tags"][:6]),
                    "tags": "、".join(item["tags"][:8]),
                    "related_signals": item["evidence"] or item["scenario"],
                },
            }
        )
    for item in match_rows:
        suggestions.append(
            {
                "id": f"match-{item['product_name']}",
                "kind": "match",
                "title": f"货盘匹配：{item['product_name']}",
                "summary": f"{item['demand_scenario']} · 得分 {item['score']} · {'、'.join(str(r) for r in item['reasons'][:3])}",
                "params": {
                    "product_categories": item["product_category"] or "",
                    "related_signals": item["demand_scenario"],
                },
            }
        )
    for signal in signals[:5]:
        if not signal.raw_content.strip():
            continue
        suggestions.append(
            {
                "id": signal.id,
                "kind": "signal",
                "title": signal.raw_content[:40],
                "summary": signal.raw_content,
                "params": {
                    "related_signals": signal.raw_content,
                    "goal_value": "",
                },
            }
        )

    return {
        "signals": signal_rows,
        "demands": demands,
        "matches": match_rows,
        "strategies": strategy_rows,
        "suggestions": suggestions[:16],
    }


@router.post("/matches/run")
def run_matches(
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    profiles = (
        runtime.db.query(DemandProfile)
        .filter(
            DemandProfile.tenant_id == runtime.tenant_id,
            DemandProfile.industry_id == runtime.industry_id,
            DemandProfile.scenario != "待分类",
        )
        .all()
    )
    capabilities = (
        runtime.db.query(Capability)
        .filter(Capability.tenant_id == runtime.tenant_id)
        .filter(Capability.industry_id == runtime.industry_id)
        .all()
    )
    total = 0
    for profile in profiles:
        runtime.db.query(MatchResult).filter(MatchResult.demand_id == profile.id).delete(
            synchronize_session=False
        )
        scored = []
        for capability in capabilities:
            score, reasons = score_match_profile(profile, capability)
            scored.append((score, capability, reasons))
        scored.sort(key=lambda item: item[0], reverse=True)
        for score, capability, reasons in scored[:5]:
            runtime.db.add(
                MatchResult(
                    tenant_id=runtime.tenant_id,
                    demand_id=profile.id,
                    product_id=capability.id,
                    score=score,
                    reasons_json=reasons,
                )
            )
            total += 1
    runtime.db.commit()
    return {"matched": total, "demands": len(profiles)}


@router.get("/executions")
def list_executions(limit: int = 50, runtime: Runtime = Depends(get_runtime)) -> list[dict]:
    rows = (
        runtime.db.query(StrategyExecution)
        .filter(StrategyExecution.tenant_id == runtime.tenant_id)
        .filter(StrategyExecution.industry_id == runtime.industry_id)
        .order_by(StrategyExecution.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": row.id,
            "strategy_id": row.strategy_id,
            "status": row.status,
            "result": row.result_json,
            "metrics": row.metrics_json,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.post("/trigger")
def trigger_flywheel(
    payload: FlywheelTriggerIn,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    return runtime.flywheel.trigger(
        runtime.tenant_id,
        payload.signal_text,
        customer_id=payload.customer_id,
        conversation_id=payload.conversation_id,
        source_type=payload.source_type,
        industry_id=runtime.industry_id,
    )


@router.post("/{cycle_id}/adopt")
def adopt_cycle(
    cycle_id: str,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    try:
        return runtime.flywheel.adopt(runtime.tenant_id, cycle_id)
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/run-auto")
def run_auto(
    limit: int = 5,
    collect_topics: bool = True,
    runtime: Runtime = Depends(get_runtime),
    _auth: dict = Depends(require_roles("admin", "operator")),
) -> dict:
    automation = FlywheelAutomation(runtime.db, runtime.flywheel)
    return automation.run(
        runtime.tenant_id,
        pending_limit=limit,
        collect_topics=collect_topics,
    )


@router.get("/status")
def flywheel_status(runtime: Runtime = Depends(get_runtime)) -> dict:
    pending = (
        runtime.db.query(DemandSignal)
        .filter(
            DemandSignal.tenant_id == runtime.tenant_id,
            DemandSignal.status == "new",
        )
        .count()
    )
    topics = (
        runtime.db.query(DemandSignal)
        .filter(
            DemandSignal.tenant_id == runtime.tenant_id,
            DemandSignal.source_type == "topic",
        )
        .count()
    )
    return {
        "pending_signals": pending,
        "topic_signals": topics,
        "auto_enabled": get_settings().flywheel_auto_enabled,
        "last_run": last_run_state,
    }


@router.get("/dashboard")
def flywheel_dashboard(runtime: Runtime = Depends(get_runtime)) -> dict:
    aggregate = (
        runtime.db.query(
            func.count(FlywheelMetric.id),
            func.avg(FlywheelMetric.closed_loop_days),
            func.sum(FlywheelMetric.hit_count),
            func.sum(FlywheelMetric.adopted_count),
            func.avg(FlywheelMetric.roi),
        )
        .filter(FlywheelMetric.tenant_id == runtime.tenant_id)
        .one()
    )
    recent = (
        runtime.db.query(StrategyExecution)
        .filter(StrategyExecution.tenant_id == runtime.tenant_id)
        .order_by(StrategyExecution.created_at.desc())
        .limit(20)
        .all()
    )
    return {
        "total_cycles": aggregate[0] or 0,
        "avg_closed_loop_days": round(aggregate[1] or 0, 2),
        "total_hit_count": aggregate[2] or 0,
        "total_adopted_count": aggregate[3] or 0,
        "avg_roi": round(aggregate[4] or 0, 2),
        "recent_cycles": [
            {
                "id": row.id,
                "status": row.status,
                "strategy_id": row.strategy_id,
                "result": row.result_json,
                "metrics": row.metrics_json,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in recent
        ],
    }
