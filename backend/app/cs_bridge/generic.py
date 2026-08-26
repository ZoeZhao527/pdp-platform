from typing import Any

import httpx

from app.cs_bridge.protocol import CsPlatformAdapter, CsSession


class GenericHttpAdapter(CsPlatformAdapter):
    """通用 HTTP 适配器：通过 webhook URL + token 对接任意外部客服平台。"""

    platform = "generic_http"

    def _config(self, session: CsSession) -> dict[str, Any]:
        return session.context.get("config", {})

    def _post(self, session: CsSession, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        config = self._config(session)
        base_url = config.get("webhook_url") or config.get("base_url")
        token = config.get("token", "")
        if not base_url:
            return {
                "ok": True,
                "note": "外部客服平台未配置 webhook_url，消息已记录但未外发",
            }
        url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        with httpx.Client(timeout=10) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return {"ok": True, "status_code": resp.status_code, "body": resp.json()}

    def send_message(self, session: CsSession, text: str) -> dict[str, Any]:
        return self._post(
            session,
            "messages",
            {
                "session_id": session.session_id,
                "conversation_id": session.conversation_id,
                "external_id": session.external_id,
                "content": text,
            },
        )

    def sync_session(self, session: CsSession) -> dict[str, Any]:
        return self._post(
            session,
            "sessions/sync",
            {
                "session_id": session.session_id,
                "conversation_id": session.conversation_id,
                "external_id": session.external_id,
                "context": session.context,
            },
        )

    def handle_event(self, session: CsSession, event: dict[str, Any]) -> dict[str, Any]:
        return self._post(session, "events", {"session_id": session.session_id, "event": event})


class EchoAdapter(CsPlatformAdapter):
    """本地演示适配器：不真正外发，用于跑通客服桥接链路。"""

    platform = "echo"

    def send_message(self, session: CsSession, text: str) -> dict[str, Any]:
        return {"ok": True, "reply": f"[外部客服平台] {text}"}

    def sync_session(self, session: CsSession) -> dict[str, Any]:
        return {"ok": True, "session_id": session.session_id, "synced": True}

    def handle_event(self, session: CsSession, event: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "event_type": event.get("event_type"), "received": True}

