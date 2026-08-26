from typing import Any

from pydantic import BaseModel, Field


class WebhookIn(BaseModel):
    external_id: str = Field(..., description="渠道侧用户或会话 ID")
    content: str
    customer_id: str | None = None
    conversation_id: str | None = None
    source_type: str = "message"


class WebhookOut(BaseModel):
    conversation_id: str
    route: str
    reply: str | None = None
    handoff: bool = False


class CsSessionIn(BaseModel):
    conversation_id: str
    external_id: str | None = None
    platform: str = "generic_http"
    context: dict[str, Any] | None = None


class CsEventIn(BaseModel):
    conversation_id: str
    event_type: str = "message"
    content: str | None = None
    payload: dict[str, Any] | None = None


class MessageCreate(BaseModel):
    content: str
    direction: str = "out"
    source: str = "manual"


class FlywheelTriggerIn(BaseModel):
    signal_text: str
    customer_id: str | None = None
    conversation_id: str | None = None
    source_type: str = "message"


class AgentRunIn(BaseModel):
    agent_key: str = "ops_assistant"
    conversation_id: str | None = None
    input: dict[str, Any] | None = None


class GuardrailRuleIn(BaseModel):
    rule_type: str = "sensitive_word"
    name: str
    pattern: list[str]
    action: str = "block"
    enabled: bool = True

