from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import Runtime, get_runtime
from app.models import Channel
from app.schemas import WebhookIn, WebhookOut

router = APIRouter(prefix="/api/v1/channels", tags=["channels"])


@router.post("/{channel_type}/webhook", response_model=WebhookOut)
def channel_webhook(
    channel_type: str,
    payload: WebhookIn,
    runtime: Runtime = Depends(get_runtime),
) -> WebhookOut:
    channel = (
        runtime.db.query(Channel)
        .filter(
            Channel.tenant_id == runtime.tenant_id,
            Channel.channel_type == channel_type,
            Channel.enabled.is_(True),
        )
        .first()
    )
    if channel is None:
        raise HTTPException(status_code=404, detail=f"渠道未启用: {channel_type}")
    result = runtime.message_router.handle_incoming(channel, payload)
    return WebhookOut(
        conversation_id=result["conversation_id"],
        route=result["route"],
        reply=result.get("reply"),
        handoff=result.get("handoff", False),
    )

