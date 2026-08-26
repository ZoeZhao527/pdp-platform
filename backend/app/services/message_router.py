from typing import Any

from sqlalchemy.orm import Session

from app.channels.gateway import ChannelGateway
from app.cs_bridge.service import CsBridgeService
from app.customers.service import CustomerService
from app.guardrails.service import GuardrailService
from app.llm_gateway.router import LLMRouter
from app.memory.service import MemoryService
from app.models import Channel, Conversation, DemandSignal, Message
from app.orchestration.engine import OrchestrationEngine


CS_KEYWORDS = ["客服", "人工", "售后", "转人工", "退款", "投诉"]


class MessageRouterService:
    def __init__(
        self,
        db: Session,
        tenant_id: str,
        industry_id: str | None,
        llm_router: LLMRouter,
        guardrails: GuardrailService,
        cs_bridge: CsBridgeService,
        engine: OrchestrationEngine,
        memory: MemoryService,
        gateway: ChannelGateway,
    ) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self.industry_id = industry_id
        self.llm_router = llm_router
        self.guardrails = guardrails
        self.cs_bridge = cs_bridge
        self.engine = engine
        self.memory = memory
        self.gateway = gateway

    def _classify(self, content: str) -> str:
        return "cs" if any(kw in content for kw in CS_KEYWORDS) else "ops"

    def _get_or_create_conversation(
        self,
        channel: Channel,
        external_id: str,
        conversation_id: str | None,
        customer_id: str | None,
        content: str,
    ) -> Conversation:
        if conversation_id:
            conversation = self.db.get(Conversation, conversation_id)
            if conversation:
                return conversation
        conversation = (
            self.db.query(Conversation)
            .filter(
                Conversation.tenant_id == self.tenant_id,
                Conversation.channel_id == channel.id,
                Conversation.external_id == external_id,
            )
            .order_by(Conversation.created_at.desc())
            .first()
        )
        if conversation:
            return conversation
        conversation = Conversation(
            tenant_id=self.tenant_id,
            channel_id=channel.id,
            external_id=external_id,
            customer_id=None,
            conversation_type=self._classify(content),
            status="open",
            title=content[:40],
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def _save_message(
        self,
        conversation: Conversation,
        direction: str,
        content: str,
        source: str,
        payload: dict[str, Any] | None = None,
    ) -> Message:
        message = Message(
            tenant_id=self.tenant_id,
            conversation_id=conversation.id,
            direction=direction,
            source=source,
            content=content,
            payload_json=payload,
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def handle_incoming(self, channel: Channel, payload: Any) -> dict[str, Any]:
        conversation = self._get_or_create_conversation(
            channel,
            payload.external_id,
            payload.conversation_id,
            payload.customer_id,
            payload.content,
        )
        if not conversation.customer_id:
            customers = CustomerService(self.db)
            customer = customers.get_or_create(
                self.tenant_id,
                payload.customer_id or payload.external_id,
                name=payload.customer_id or None,
                industry_id=self.industry_id,
            )
            conversation.customer_id = customer.id
            customers.update_profile_from_text(self.tenant_id, customer.id, payload.content)
            self.db.commit()
        incoming = self._save_message(
            conversation,
            "in",
            payload.content,
            "channel",
            {"source_type": payload.source_type},
        )
        signal = DemandSignal(
            tenant_id=self.tenant_id,
            customer_id=conversation.customer_id,
            conversation_id=conversation.id,
            source_type=payload.source_type,
            raw_content=payload.content,
        )
        self.db.add(signal)
        self.db.commit()

        if conversation.conversation_type == "cs":
            config = (channel.config_json or {}).get("cs_platform", {})
            platform = config.get("platform", "echo")
            result = self.cs_bridge.forward_message(
                self.db,
                self.tenant_id,
                conversation,
                payload.content,
                platform=platform,
                config=config,
            )
            reply = result.get("reply")
            if reply:
                saved = self._save_message(conversation, "out", reply, "cs_platform")
                guardrail = self.guardrails.check(self.tenant_id, reply, message_id=saved.id)
                if guardrail.action == "block":
                    conversation.status = "handoff"
                    reply = "该内容需要人工审核，我们已通知运营人员跟进。"
                    self._save_message(conversation, "out", reply, "guardrail")
                    self.db.commit()
                elif guardrail.action == "handoff":
                    conversation.status = "handoff"
                    reply = "已为你转接人工客服，请稍等。"
                    self._save_message(conversation, "out", reply, "guardrail")
                    self.db.commit()
            return {
                "conversation_id": conversation.id,
                "route": "cs",
                "reply": reply,
                "handoff": conversation.status == "handoff",
            }

        result = self.engine.run(
            self.tenant_id,
            agent_key="ops_assistant",
            conversation_id=conversation.id,
            input_data={"text": payload.content},
        )
        reply = result["reply"]
        saved = self._save_message(conversation, "out", reply, "agent")
        guardrail = self.guardrails.check(self.tenant_id, reply, message_id=saved.id)
        if guardrail.action == "block":
            reply = "该内容需要人工审核，我们已通知运营人员跟进。"
            self._save_message(conversation, "out", reply, "guardrail")
            self.db.commit()
        elif guardrail.action == "handoff":
            conversation.status = "handoff"
            reply = "已为你转接人工客服，请稍等。"
            self._save_message(conversation, "out", reply, "guardrail")
            self.db.commit()
        else:
            self.gateway.send(
                channel.channel_type,
                conversation.id,
                conversation.external_id,
                reply,
                channel.config_json,
            )
        return {
            "conversation_id": conversation.id,
            "route": "ops",
            "reply": reply,
            "handoff": conversation.status == "handoff",
        }
