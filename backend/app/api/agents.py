from fastapi import APIRouter, Depends

from app.agents.registry import agent_registry
from app.api.deps import Runtime, get_runtime
from app.models import AgentDef
from app.schemas import AgentRunIn

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.get("")
def list_agents(runtime: Runtime = Depends(get_runtime)) -> list[dict]:
    rows = (
        runtime.db.query(AgentDef)
        .filter(AgentDef.tenant_id == runtime.tenant_id)
        .order_by(AgentDef.created_at.asc())
        .all()
    )
    return [
        {
            "key": row.key,
            "name": row.name,
            "description": row.description,
            "enabled": row.enabled,
        }
        for row in rows
    ]


@router.post("/run")
def run_agent(
    payload: AgentRunIn,
    runtime: Runtime = Depends(get_runtime),
) -> dict:
    agent_registry.get(payload.agent_key)
    return runtime.engine.run(
        runtime.tenant_id,
        payload.agent_key,
        conversation_id=payload.conversation_id,
        input_data=payload.input or {},
    )

