from uuid import uuid4

from app.channels.base import ChannelAdapter, SendResult


class MockChannelAdapter(ChannelAdapter):
    channel_type = "mock"

    def send_message(
        self,
        conversation_id: str,
        external_id: str,
        text: str,
        channel_config: dict | None = None,
    ) -> SendResult:
        return SendResult(
            ok=True,
            message_id=f"mock-{uuid4().hex[:12]}",
            detail="Mock 渠道已发送",
        )

