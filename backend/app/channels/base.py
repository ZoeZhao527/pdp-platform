from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SendResult:
    ok: bool
    message_id: str | None = None
    detail: str | None = None


class ChannelAdapter(ABC):
    channel_type: str = ""

    @abstractmethod
    def send_message(
        self,
        conversation_id: str,
        external_id: str,
        text: str,
        channel_config: dict | None = None,
    ) -> SendResult:
        raise NotImplementedError

