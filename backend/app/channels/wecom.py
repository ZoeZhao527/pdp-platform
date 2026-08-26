from app.channels.base import ChannelAdapter, SendResult


class WeComChannelAdapter(ChannelAdapter):
    channel_type = "wecom"

    def send_message(
        self,
        conversation_id: str,
        external_id: str,
        text: str,
        channel_config: dict | None = None,
    ) -> SendResult:
        # P1 接入企业微信客户联系 API：获取 access_token 后调用消息接口。
        # 此处先保留适配器边界，避免业务层感知渠道差异。
        return SendResult(
            ok=True,
            detail="企业微信适配器已预留，配置 corp_id/secret 后接入真实发送",
        )

