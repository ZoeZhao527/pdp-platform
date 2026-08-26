from app.channels.base import ChannelAdapter, SendResult
from app.channels.mock import MockChannelAdapter
from app.channels.wecom import WeComChannelAdapter


class ChannelGateway:
    def __init__(self) -> None:
        self._adapters: dict[str, ChannelAdapter] = {}

    def register(self, adapter: ChannelAdapter) -> None:
        self._adapters[adapter.channel_type] = adapter

    def get(self, channel_type: str) -> ChannelAdapter | None:
        return self._adapters.get(channel_type)

    def send(
        self,
        channel_type: str,
        conversation_id: str,
        external_id: str,
        text: str,
        channel_config: dict | None = None,
    ) -> SendResult:
        adapter = self.get(channel_type)
        if adapter is None:
            return SendResult(ok=False, detail=f"未注册渠道适配器: {channel_type}")
        return adapter.send_message(conversation_id, external_id, text, channel_config)


channel_gateway = ChannelGateway()
channel_gateway.register(MockChannelAdapter())
channel_gateway.register(WeComChannelAdapter())

