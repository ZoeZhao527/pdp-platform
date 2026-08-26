from dataclasses import dataclass
from typing import Type, TypeVar

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.channels.gateway import ChannelGateway, channel_gateway
from app.config import get_settings
from app.cs_bridge.service import CsBridgeService
from app.db import get_db
from app.flywheel.pipeline import FlywheelService
from app.guardrails.service import GuardrailService
from app.llm_gateway.router import LLMRouter
from app.memory.service import MemoryService
from app.models import Tenant
from app.orchestration.engine import OrchestrationEngine
from app.services.message_router import MessageRouterService

ModelT = TypeVar("ModelT")


@dataclass
class Runtime:
    db: Session
    tenant_id: str
    industry_id: str | None
    llm_router: LLMRouter
    guardrails: GuardrailService
    cs_bridge: CsBridgeService
    memory: MemoryService
    engine: OrchestrationEngine
    gateway: ChannelGateway
    message_router: MessageRouterService
    flywheel: FlywheelService


def get_tenant_id(
    x_tenant_id: str = Header(default=get_settings().default_tenant_id),
    auth: dict = Depends(require_auth),
) -> str:
    """Validate X-Tenant-Id against the authenticated user's token.

    admin role can switch between tenants (manages multiple brands);
    operator / viewer are locked to their assigned tenant.
    """
    if auth.get("role") != "admin":
        token_tenant = auth.get("tenant")
        if token_tenant and x_tenant_id != token_tenant:
            raise HTTPException(status_code=403, detail="无权访问该品牌数据")
    return x_tenant_id


def get_industry_id(
    x_industry_id: str | None = Header(default=None),
) -> str | None:
    return x_industry_id or None


def get_tenant_owned(
    db: Session,
    model: Type[ModelT],
    obj_id: str,
    tenant_id: str,
) -> ModelT | None:
    """Fetch a row by primary key and verify it belongs to tenant_id.
    Returns None if not found or belongs to a different tenant.
    """
    obj = db.get(model, obj_id)
    if obj is None:
        return None
    if not hasattr(obj, "tenant_id"):
        return obj
    if obj.tenant_id != tenant_id:
        return None
    return obj


def require_tenant_owned(
    db: Session,
    model: Type[ModelT],
    obj_id: str,
    tenant_id: str,
    detail: str = "资源不存在或无权访问",
) -> ModelT:
    """Like get_tenant_owned but raises 404 on miss."""
    obj = get_tenant_owned(db, model, obj_id, tenant_id)
    if obj is None:
        raise HTTPException(status_code=404, detail=detail)
    return obj


def get_runtime(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    industry_id: str | None = Depends(get_industry_id),
) -> Runtime:
    if industry_id is None:
        tenant = db.get(Tenant, tenant_id)
        industry_id = tenant.industry_id if tenant else None
    llm_router = LLMRouter(db)
    guardrails = GuardrailService(db)
    cs_bridge = CsBridgeService()
    memory = MemoryService(db)
    engine = OrchestrationEngine(db, llm_router, memory)
    flywheel = FlywheelService(db, llm_router, engine)
    message_router = MessageRouterService(
        db,
        tenant_id,
        industry_id,
        llm_router,
        guardrails,
        cs_bridge,
        engine,
        memory,
        channel_gateway,
    )
    return Runtime(
        db=db,
        tenant_id=tenant_id,
        industry_id=industry_id,
        llm_router=llm_router,
        guardrails=guardrails,
        cs_bridge=cs_bridge,
        memory=memory,
        engine=engine,
        gateway=channel_gateway,
        message_router=message_router,
        flywheel=flywheel,
    )
