from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.cs_bridge.protocol import CsSession
from app.cs_bridge.registry import cs_bridge_registry
from app.models import AuditLog, Conversation, Message


class CsBridgeService:
    def sync_session(
        self,
        db: Session,
        tenant_id: str,
        conversation: Conversation,
        platform: str = "generic_http",
        config: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        conversation.conversation_type = "cs"
        session = CsSession(
            session_id=str(uuid4()),
            conversation_id=conversation.id,
            external_id=conversation.external_id,
            platform=platform,
            context={"config": config or {}, **(context or {})},
        )
        result = cs_bridge_registry.get(platform).sync_session(session)
        db.add(
            AuditLog(
                tenant_id=tenant_id,
                actor="system",
                action="cs_session_sync",
                entity_type="conversation",
                entity_id=conversation.id,
                after_json={"platform": platform, "result": result},
            )
        )
        db.commit()
        return {"session_id": session.session_id, "result": result}

    def forward_message(
        self,
        db: Session,
        tenant_id: str,
        conversation: Conversation,
        text: str,
        platform: str = "echo",
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session = CsSession(
            session_id=str(uuid4()),
            conversation_id=conversation.id,
            external_id=conversation.external_id,
            platform=platform,
            context={"config": config or {}},
        )
        result = cs_bridge_registry.get(platform).send_message(session, text)
        db.add(
            AuditLog(
                tenant_id=tenant_id,
                actor="system",
                action="cs_message_forward",
                entity_type="conversation",
                entity_id=conversation.id,
                after_json={"text": text, "result": result},
            )
        )
        db.commit()
        return result

    def handle_event(
        self,
        db: Session,
        tenant_id: str,
        conversation_id: str,
        event_type: str,
        content: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Message | None:
        if event_type == "message" and content:
            message = Message(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                direction="in",
                source="cs_platform",
                content=content,
                payload_json=payload,
            )
            db.add(message)
        if event_type == "handoff":
            conversation = db.get(Conversation, conversation_id)
            if conversation:
                conversation.status = "handoff"
        if event_type == "ended":
            conversation = db.get(Conversation, conversation_id)
            if conversation:
                conversation.status = "closed"
        db.commit()
        return message if event_type == "message" and content else None
