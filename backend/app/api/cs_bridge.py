from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import Runtime, get_runtime
from app.models import Channel, Conversation
from app.schemas import CsEventIn, CsSessionIn

router = APIRouter(prefix="/api/v1/cs-bridge", tags=["cs-bridge"])


@router.post("/sessions")
def sync_session(
    payload: CsSessionIn,
    runtime: Runtime = Depends(get_runtime),
) -> dict:
    conversation = runtime.db.get(Conversation, payload.conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    channel = runtime.db.get(Channel, conversation.channel_id)
    config = (channel.config_json or {}).get("cs_platform", {}) if channel else {}
    result = runtime.cs_bridge.sync_session(
        runtime.db,
        runtime.tenant_id,
        conversation,
        platform=payload.platform,
        config=config,
        context=payload.context,
    )
    return {"ok": True, **result}


@router.post("/events")
def handle_event(
    payload: CsEventIn,
    runtime: Runtime = Depends(get_runtime),
) -> dict:
    conversation = runtime.db.get(Conversation, payload.conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    runtime.cs_bridge.handle_event(
        runtime.db,
        runtime.tenant_id,
        conversation.id,
        payload.event_type,
        payload.content,
        payload.payload,
    )
    return {"ok": True, "event_type": payload.event_type}

