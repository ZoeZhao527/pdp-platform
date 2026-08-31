"""飞书自建应用接入：封装 OpenAPI 调用 + 群聊指令处理。

指令链路：飞书群消息 -> webhook/handle -> handle_feishu_command -> 写库/查库 -> 回复到群。
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from logging import getLogger
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import FeedbackEvent, KpiMetric, Strategy

logger = getLogger(__name__)

FEISHU_BASE = "https://open.feishu.cn"


@dataclass
class FeishuMessage:
    message_id: str
    sender: str
    text: str
    created_at: str
    msg_type: str = "text"


class FeishuClient:
    """飞书 OpenAPI 薄封装：换 token / 拉群消息 / 发群消息。"""

    def __init__(
        self,
        app_id: str = "",
        app_secret: str = "",
        chat_id: str = "",
        mock: bool = True,
        command_prefix: str = "@运营中台",
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.chat_id = chat_id
        self.mock = mock or not app_id or not app_secret
        self.command_prefix = command_prefix
        self._token: str = ""
        self._token_expire: float = 0.0
        self._user_cache: dict[str, str] = {}

    def _get_tenant_access_token(self) -> str:
        if self._token and time.time() < self._token_expire - 60:
            return self._token
        resp = httpx.post(
            f"{FEISHU_BASE}/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["tenant_access_token"]
        self._token_expire = time.time() + int(data.get("expire", 7200))
        return self._token

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._get_tenant_access_token()}"}

    def get_user_name(self, user_id: str) -> str:
        """Resolve open_id to user name, with in-memory cache."""
        if not user_id or user_id in ("unknown", ""):
            return "系统消息"
        if user_id in self._user_cache:
            return self._user_cache[user_id]
        if self.mock:
            return user_id[:8]
        try:
            resp = httpx.get(
                f"{FEISHU_BASE}/open-apis/contact/v3/users/{user_id}",
                params={"user_id_type": "open_id"},
                headers=self._auth_headers(),
                timeout=10,
            )
            if resp.status_code == 200:
                name = resp.json().get("data", {}).get("user", {}).get("name", "")
                if name:
                    self._user_cache[user_id] = name
                    return name
        except Exception:
            pass
        # Fallback: show truncated ID
        short = user_id.replace("ou_", "")[:8]
        return f"成员_{short}"

    def list_messages(self, limit: int = 10) -> list[FeishuMessage]:
        if self.mock:
            return _mock_messages(limit)
        resp = httpx.get(
            f"{FEISHU_BASE}/open-apis/im/v1/messages",
            params={
                "container_id_type": "chat",
                "container_id": self.chat_id,
                "page_size": min(limit, 50),
            },
            headers=self._auth_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("data", {}).get("items", [])
        messages: list[FeishuMessage] = []
        for item in items:
            body = item.get("body", {})
            content_str = body.get("content", "{}")
            try:
                content = json.loads(content_str)
            except (json.JSONDecodeError, TypeError):
                content = {}
            text = content.get("text", "")
            if not text and "template" in content:
                text = _render_template_message(content)
            if not text:
                text = content_str
            msg_type = item.get("msg_type", "text")
            sender_id = item.get("sender", {}).get("id", "unknown")
            messages.append(
                FeishuMessage(
                    message_id=item.get("message_id", ""),
                    sender=sender_id,
                    text=text,
                    created_at=item.get("create_time", ""),
                    msg_type=msg_type,
                )
            )
        return messages[:limit]

    def send_message(self, text: str) -> dict[str, Any]:
        if self.mock:
            logger.info("[飞书 mock] 发送消息: %s", text)
            return {"ok": True, "message_id": "mock", "detail": "mock 模式，未真实发送"}
        resp = httpx.post(
            f"{FEISHU_BASE}/open-apis/im/v1/messages",
            params={"receive_id_type": "chat_id"},
            headers=self._auth_headers(),
            json={
                "receive_id": self.chat_id,
                "msg_type": "text",
                "content": json.dumps({"text": text}),
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "ok": data.get("code", 0) == 0,
            "message_id": data.get("data", {}).get("message_id", ""),
            "detail": data.get("msg", ""),
        }

    def send_card(self, header_title: str, elements: list, header_template: str = "blue") -> dict[str, Any]:
        """发送飞书互动卡片消息，支持标题/分栏/分隔线/富文本。"""
        if self.mock:
            logger.info("[飞书 mock] 发送卡片: %s", header_title)
            return {"ok": True, "message_id": "mock", "detail": "mock 模式，未真实发送"}
        card = {
            "header": {
                "title": {"tag": "plain_text", "content": header_title},
                "template": header_template,
            },
            "elements": elements,
        }
        resp = httpx.post(
            f"{FEISHU_BASE}/open-apis/im/v1/messages",
            params={"receive_id_type": "chat_id"},
            headers=self._auth_headers(),
            json={
                "receive_id": self.chat_id,
                "msg_type": "interactive",
                "content": json.dumps(card),
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "ok": data.get("code", 0) == 0,
            "message_id": data.get("data", {}).get("message_id", ""),
            "detail": data.get("msg", ""),
        }


_client_cache: dict[str, FeishuClient] = {}


def get_feishu_client(tenant_id: str = "") -> FeishuClient:
    """按租户构建 FeishuClient：优先从 DB 读 feishu_configs，回退到 env 变量。

    messaging_enabled=False 时自动进入 mock 模式（不发消息）。
    """
    if tenant_id and tenant_id in _client_cache:
        return _client_cache[tenant_id]
    s = get_settings()
    app_id = s.feishu_app_id
    app_secret = s.feishu_app_secret
    chat_id = s.feishu_chat_id
    mock = s.feishu_mock or not s.feishu_enabled
    # 从 DB 读取租户级飞书配置（优先于 env）
    if tenant_id:
        from app.db import SessionLocal
        from app.models import FeishuConfig
        with SessionLocal() as db:
            cfg = db.query(FeishuConfig).filter(FeishuConfig.tenant_id == tenant_id).first()
        if cfg and cfg.enabled and cfg.app_id and cfg.app_secret:
            app_id = cfg.app_id
            app_secret = cfg.app_secret
            chat_id = cfg.chat_id or ""
            mock = not cfg.messaging_enabled
    client = FeishuClient(
        app_id=app_id,
        app_secret=app_secret,
        chat_id=chat_id,
        mock=mock,
        command_prefix=s.feishu_command_prefix,
    )
    _client_cache[tenant_id] = client
    return client


def invalidate_feishu_cache(tenant_id: str = "") -> None:
    """清除租户飞书 client 缓存（配置更新后调用）。"""
    _client_cache.pop(tenant_id, None)


def get_tenant_id_by_app_id(app_id: str) -> str:
    """按飞书 app_id 反查租户 ID（webhook 路由用）。"""
    if not app_id:
        return ""
    from app.db import SessionLocal
    from app.models import FeishuConfig
    with SessionLocal() as db:
        cfg = db.query(FeishuConfig).filter(FeishuConfig.app_id == app_id).first()
        if cfg:
            return cfg.tenant_id
    # 回退到默认租户（兼容旧配置）
    return get_settings().default_tenant_id


def handle_feishu_command(
    text: str,
    db: Session,
    tenant_id: str,
    industry_id: str | None,
    client: FeishuClient | None = None,
) -> str:
    """解析飞书群聊指令并执行，返回回复文本。"""
    client = client or get_feishu_client(tenant_id)
    raw = text.strip()
    if raw.startswith(client.command_prefix):
        raw = raw[len(client.command_prefix) :].strip()
    raw = re.sub(r"^@\S+\s*", "", raw).strip()

    if "回传" in raw or "反馈" in raw:
        return _cmd_feedback(raw, db, tenant_id, industry_id)
    if "策略" in raw and any(kw in raw for kw in ("查看", "获取", "当前", "列表")):
        return _cmd_list_strategies(db, tenant_id, industry_id)
    if "托管" in raw:
        return _cmd_toggle_managed(db, tenant_id, industry_id)

    return """未识别的指令。支持：
1) 回传：今日卖卡12单
2) 查看当前策略
3) 开启策略托管"""


def _cmd_feedback(raw: str, db: Session, tenant_id: str, industry_id: str | None) -> str:
    num = _parse_number(raw)
    action = _extract_action(raw)
    event = FeedbackEvent(
        tenant_id=tenant_id,
        industry_id=industry_id,
        action=action,
        amount=num,
        note=raw,
        occurred_at=_today_str(),
    )
    db.add(event)
    updated = _try_update_kpi(db, tenant_id, industry_id, action, num)
    db.commit()
    kpi_hint = f"，已自动更新「{updated}」KPI 实际值" if updated else ""
    return f"已记录回传：{action} {num}{kpi_hint}"


def _cmd_list_strategies(db: Session, tenant_id: str, industry_id: str | None) -> str:
    rows = (
        db.query(Strategy)
        .filter(Strategy.tenant_id == tenant_id)
        .filter(Strategy.industry_id == industry_id if industry_id else True)
        .order_by(Strategy.created_at.desc())
        .limit(5)
        .all()
    )
    if not rows:
        return "当前没有策略。可在策略沉淀中心或指令中心生成策略。"
    lines = ["最近策略："]
    for i, row in enumerate(rows, 1):
        status = "托管" if row.managed else row.status
        lines.append(f"{i}. {row.name} [{row.strategy_type}] - {status}")
    return "\n".join(lines)


def _cmd_toggle_managed(db: Session, tenant_id: str, industry_id: str | None) -> str:
    row = (
        db.query(Strategy)
        .filter(Strategy.tenant_id == tenant_id)
        .filter(Strategy.industry_id == industry_id if industry_id else True)
        .order_by(Strategy.created_at.desc())
        .first()
    )
    if row is None:
        return "没有可托管的策略。请先在指令中心生成策略后再开启托管。"
    row.managed = not row.managed
    row.status = "托管" if row.managed else "草稿"
    db.commit()
    state = "已开启" if row.managed else "已关闭"
    return f"策略「{row.name}」托管{state}"


_CN_NUM = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _parse_number(text: str) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if match:
        return float(match.group(1))
    for ch, val in _CN_NUM.items():
        if ch in text:
            return float(val)
    return 0.0


def _extract_action(text: str) -> str:
    """从「回传：今日卖卡12单」中提取「卖卡」这类动作。"""
    cleaned = re.sub(r"^(回传|反馈)[:：\s]*", "", text)
    cleaned = re.sub(r"今日|昨日|本周|今日的?", "", cleaned)
    cleaned = re.sub(r"[\d零一二两三四五六七八九十百千\.]+", "", cleaned)
    cleaned = re.sub(r"单|元|人|次$", "", cleaned).strip()
    return cleaned or "回传数据"


def _try_update_kpi(db: Session, tenant_id: str, industry_id: str | None, action: str, amount: float) -> str:
    """找到指标名包含动作关键词的 KPI，累加 actual。"""
    if not action or amount == 0:
        return ""
    rows = (
        db.query(KpiMetric)
        .filter(KpiMetric.tenant_id == tenant_id)
        .filter(KpiMetric.industry_id == industry_id if industry_id else True)
        .order_by(KpiMetric.created_at.desc())
        .all()
    )
    for row in rows:
        if action in row.metric or row.metric in action:
            row.actual += amount
            return row.metric
    return ""


def _today_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _render_template_message(content: dict) -> str:
    """将飞书系统通知消息（邀请入群、设为管理员等）解析为可读文本。"""
    template = content.get("template", "")
    from_user = content.get("from_user", [])
    to_chatters = content.get("to_chatters", [])
    from_str = "、".join(from_user) if from_user else ""
    to_str = "、".join(to_chatters) if to_chatters else ""
    if "invited" in template:
        if to_str:
            return f"{from_str} 邀请 {to_str} 加入了群聊"
        return f"{from_str} 发起了邀请"
    if "GroupOwner" in template and "administrators" in template:
        if to_str:
            return f"群主将 {to_str} 设为了群管理员"
        return "群管理员有变动"
    if "added" in template and "administrators" in template:
        if to_str:
            return f"{from_str} 将 {to_str} 设为了群管理员"
        return "群管理员有变动"
    return f"[系统消息] {template}"


def _mock_messages(limit: int) -> list[FeishuMessage]:
    samples = [
        ("运营-小王", "回传：今日卖卡8单"),
        ("运营-Lisa", "查看当前策略"),
        ("运营-小王", "开启策略托管"),
        ("飞书机器人", "策略「美业周年庆拉新」托管已开启"),
        ("运营-Lisa", "回传：本周复购32单"),
    ]
    now = time.time()
    return [
        FeishuMessage(
            message_id=f"mock_{i}",
            sender=s,
            text=t,
            created_at=str(int(now - i * 120)),
        )
        for i, (s, t) in enumerate(samples[:limit])
    ]
