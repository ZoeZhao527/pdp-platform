from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import Runtime, get_runtime
from app.models import GuardrailRule
from app.services.asset_resolver import resolve_assets
from app.schemas import GuardrailRuleIn

router = APIRouter(prefix="/api/v1/guardrails", tags=["guardrails"])


@router.get("/rules")
def list_rules(runtime: Runtime = Depends(get_runtime)) -> list[dict]:
    rows = resolve_assets(runtime.db, GuardrailRule, runtime.tenant_id)
    return [
        {
            "id": row.id,
            "name": row.name,
            "rule_type": row.rule_type,
            "action": row.action,
            "pattern": row.pattern_json.get("keywords", []),
            "enabled": row.enabled,
            "is_platform": row.is_platform,
            "platform_ref": row.platform_ref,
        }
        for row in rows
    ]


@router.post("/rules")
def create_rule(payload: GuardrailRuleIn, runtime: Runtime = Depends(get_runtime)) -> dict:
    rule = GuardrailRule(
        tenant_id=runtime.tenant_id,
        rule_type=payload.rule_type,
        name=payload.name,
        pattern_json={"keywords": payload.pattern},
        action=payload.action,
        enabled=payload.enabled,
    )
    runtime.db.add(rule)
    runtime.db.commit()
    runtime.db.refresh(rule)
    return {"id": rule.id, "name": rule.name}


@router.put("/rules/{rule_id}")
def update_rule(
    rule_id: str,
    payload: GuardrailRuleIn,
    runtime: Runtime = Depends(get_runtime),
) -> dict:
    rule = runtime.db.get(GuardrailRule, rule_id)
    if rule is None or rule.tenant_id != runtime.tenant_id:
        raise HTTPException(status_code=404, detail="规则不存在")
    rule.rule_type = payload.rule_type
    rule.name = payload.name
    rule.pattern_json = {"keywords": payload.pattern}
    rule.action = payload.action
    rule.enabled = payload.enabled
    runtime.db.commit()
    return {"id": rule.id, "name": rule.name}


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str, runtime: Runtime = Depends(get_runtime)) -> dict:
    rule = runtime.db.get(GuardrailRule, rule_id)
    if rule is None or rule.tenant_id != runtime.tenant_id:
        raise HTTPException(status_code=404, detail="规则不存在")
    runtime.db.delete(rule)
    runtime.db.commit()
    return {"ok": True}
