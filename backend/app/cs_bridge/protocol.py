from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CsSession:
    session_id: str
    conversation_id: str
    external_id: str
    platform: str
    context: dict[str, Any] = field(default_factory=dict)


class CsPlatformAdapter(ABC):
    platform: str = "generic_http"

    @abstractmethod
    def send_message(self, session: CsSession, text: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def sync_session(self, session: CsSession) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def handle_event(self, session: CsSession, event: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

