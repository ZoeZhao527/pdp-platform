from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import Runtime, get_runtime
from app.models import Channel, Conversation, Message
from app.schemas import MessageCreate

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.get("")
def list_conversations(
    status: str | None = None,
    conversation_type: str | None = None,
    runtime: Runtime = Depends(get_runtime),
) -> list[dict]:
    query = runtime.db.query(Conversation).filter(Conversation.tenant_id == runtime.tenant_id)
    if status:
        query = query.filter(Conversation.status == status)
    if conversation_type:
        query = query.filter(Conversation.conversation_type == conversation_type)
    rows = query.order_by(Conversation.created_at.desc()).limit(100).all()
    return [
        {
            "id": row.id,
            "external_id": row.external_id,
            "channel_id": row.channel_id,
            "conversation_type": row.conversation_type,
            "status": row.status,
            "title": row.title,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in rows
    ]


@router.get("/{conversation_id}/messages")
def list_messages(
    conversation_id: str,
    runtime: Runtime = Depends(get_runtime),
) -> list[dict]:
    rows = (
        runtime.db.query(Message)
        .filter(
            Message.tenant_id == runtime.tenant_id,
            Message.conversation_id == conversation_id,
        )
        .order_by(Message.created_at.asc())
        .all()
    )
    return [
        {
            "id": row.id,
            "direction": row.direction,
            "source": row.source,
            "content": row.content,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.post("/{conversation_id}/messages")
def send_message(
    conversation_id: str,
    payload: MessageCreate,
    runtime: Runtime = Depends(get_runtime),
) -> dict:
    conversation = runtime.db.get(Conversation, conversation_id)
    if conversation is None or conversation.tenant_id != runtime.tenant_id:
        raise HTTPException(status_code=404, detail="会话不存在")
    message = Message(
        tenant_id=runtime.tenant_id,
        conversation_id=conversation.id,
        direction=payload.direction,
        source=payload.source,
        content=payload.content,
    )
    runtime.db.add(message)
    runtime.db.commit()
    runtime.db.refresh(message)

    if payload.direction == "out":
        guardrail = runtime.guardrails.check(runtime.tenant_id, payload.content, message_id=message.id)
        if guardrail.passed:
            channel = runtime.db.get(Channel, conversation.channel_id)
            if channel:
                runtime.gateway.send(
                    channel.channel_type,
                    conversation.id,
                    conversation.external_id,
                    payload.content,
                    channel.config_json,
                )
    return {
        "id": message.id,
        "direction": message.direction,
        "source": message.source,
        "content": message.content,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }

