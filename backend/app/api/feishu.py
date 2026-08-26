"""飞书接口路由：拉消息 / 发消息 / 指令处理 / webhook 回调。

前三个接口需要登录鉴权；/webhook/feishu 公开，供飞书事件订阅回调。
"""

from __future__ import annotations

import json
from logging import getLogger
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.auth import require_auth
from app.config import get_settings
from app.db import SessionLocal
from app.integrations.feishu import (
    get_feishu_client,
    get_tenant_id_by_app_id,
    handle_feishu_command,
    invalidate_feishu_cache,
)
from app.integrations.feishu_parser import process_feishu_message
from app.models import FeedbackEvent, FeishuConfig, Tenant
from app.services.daily_brief import get_today_briefs, trigger_brief

logger = getLogger(__name__)

router = APIRouter(tags=["feishu"])


class FeishuSendIn(BaseModel):
    text: str


class FeishuHandleIn(BaseModel):
    text: str


class BriefTriggerIn(BaseModel):
    report_type: str  # morning | evening


class FeishuConfigIn(BaseModel):
    app_id: str = ""
    app_secret: str = ""
    chat_id: str = ""
    verification_token: str = ""
    encrypt_key: str = ""
    enabled: bool = False
    messaging_enabled: bool = False


@router.get("/api/v1/feishu/config")
def feishu_config(_auth: dict = Depends(require_auth)) -> dict:
    """返回当前租户的飞书配置（app_secret 脱敏显示）。"""
    with SessionLocal() as db:
        cfg = db.query(FeishuConfig).filter(FeishuConfig.tenant_id == _auth["tenant"]).first()
        if not cfg:
            return {
                "app_id": "",
                "app_secret": "",
                "chat_id": "",
                "verification_token": "",
                "encrypt_key": "",
                "enabled": False,
                "messaging_enabled": False,
                "configured": False,
            }
        return {
            "app_id": cfg.app_id,
            "app_secret": "****" if cfg.app_secret else "",
            "chat_id": cfg.chat_id,
            "verification_token": cfg.verification_token,
            "encrypt_key": cfg.encrypt_key,
            "enabled": cfg.enabled,
            "messaging_enabled": cfg.messaging_enabled,
            "configured": True,
        }


@router.put("/api/v1/feishu/config")
def update_feishu_config(payload: FeishuConfigIn, _auth: dict = Depends(require_auth)) -> dict:
    """保存或更新当前租户的飞书配置。"""
    tenant_id = _auth["tenant"]
    with SessionLocal() as db:
        cfg = db.query(FeishuConfig).filter(FeishuConfig.tenant_id == tenant_id).first()
        if cfg is None:
            cfg = FeishuConfig(tenant_id=tenant_id)
            db.add(cfg)
        cfg.app_id = payload.app_id
        # 空字符串表示不更新 secret（脱敏接口返回 ****，前端回传空则保留原值）
        if payload.app_secret and payload.app_secret != "****":
            cfg.app_secret = payload.app_secret
        cfg.chat_id = payload.chat_id
        cfg.verification_token = payload.verification_token
        cfg.encrypt_key = payload.encrypt_key
        cfg.enabled = payload.enabled
        cfg.messaging_enabled = payload.messaging_enabled
        db.commit()
    invalidate_feishu_cache(tenant_id)
    return {"ok": True, "detail": "飞书配置已保存"}


@router.post("/api/v1/feishu/test")
def feishu_test(_auth: dict = Depends(require_auth)) -> dict:
    """测试飞书连接：获取 tenant_access_token。"""
    client = get_feishu_client(_auth["tenant"])
    if not client.app_id or not client.app_secret:
        return {"ok": False, "detail": "请先填写 App ID 和 App Secret"}
    try:
        token = client._get_tenant_access_token()
        return {"ok": True, "detail": f"连接成功，token 前 8 位: {token[:8]}..."}
    except Exception as exc:
        return {"ok": False, "detail": f"连接失败: {exc}"}


@router.get("/api/v1/feishu/messages")
def feishu_messages(limit: int = 20, _auth: dict = Depends(require_auth)) -> list[dict]:
    client = get_feishu_client(_auth["tenant"])
    msgs = client.list_messages(limit=limit)
    result: list[dict] = []
    for m in msgs:
        is_system = not m.sender or m.sender == "unknown"
        sender_name = "系统消息" if is_system else client.get_user_name(m.sender)
        # Format timestamp: Feishu uses millisecond epoch
        ts = ""
        if m.created_at:
            try:
                ts_int = int(m.created_at)
                if ts_int > 1e12:
                    ts_int = int(ts_int / 1000)
                from datetime import datetime
                ts = datetime.fromtimestamp(ts_int).strftime("%m-%d %H:%M")
            except (ValueError, OSError):
                ts = m.created_at
        # Categorize message
        msg_type_label = "系统" if is_system else ("卡片" if m.msg_type in ("post", "interactive") else "文字")
        result.append({
            "message_id": m.message_id,
            "sender": sender_name,
            "sender_id": m.sender,
            "text": m.text[:200] if m.text else "",
            "created_at": ts,
            "raw_timestamp": m.created_at,
            "msg_type": msg_type_label,
            "is_system": is_system,
        })
    return result


@router.post("/api/v1/feishu/send")
def feishu_send(payload: FeishuSendIn, _auth: dict = Depends(require_auth)) -> dict:
    client = get_feishu_client(_auth["tenant"])
    return client.send_message(payload.text)


@router.post("/api/v1/feishu/handle")
def feishu_handle(payload: FeishuHandleIn, _auth: dict = Depends(require_auth)) -> dict:
    with SessionLocal() as db:
        tenant = db.get(Tenant, _auth["tenant"])
        industry_id = tenant.industry_id if tenant else None
        reply = handle_feishu_command(payload.text, db, _auth["tenant"], industry_id)
    return {"reply": reply}


@router.get("/api/v1/feishu/summary")
def feishu_summary(_auth: dict = Depends(require_auth)) -> dict:
    """今日飞书回传统计：消息数、解析数、操作类型分布、KPI更新数。"""
    from datetime import datetime, date
    today = date.today().isoformat()
    with SessionLocal() as db:
        # Count feedback events from Feishu today
        rows = (
            db.query(FeedbackEvent)
            .filter(FeedbackEvent.tenant_id == _auth["tenant"])
            .filter(FeedbackEvent.created_at >= today)
            .all()
        )
        action_counts: dict[str, int] = {}
        total_amount = 0.0
        for row in rows:
            action = row.action or "其他"
            action_counts[action] = action_counts.get(action, 0) + 1
            total_amount += row.amount or 0
        return {
            "today_feedback_count": len(rows),
            "action_breakdown": action_counts,
            "total_amount": total_amount,
            "feedback_items": [
                {
                    "action": r.action,
                    "amount": r.amount,
                    "note": (r.note or "")[:80],
                    "occurred_at": r.occurred_at or "",
                }
                for r in rows[:10]
            ],
        }


@router.post("/webhook/feishu")
async def feishu_webhook(request: Request) -> dict:
    """飞书事件订阅回调：处理 url_verification + 群消息事件。"""
    body = await request.json()
    raw = json.dumps(body, ensure_ascii=False)[:2000]
    print(f"[FEISHU_WEBHOOK] raw_body={raw}", flush=True)
    # 1) url_verification challenge 回包
    if "challenge" in body:
        return {"challenge": body["challenge"]}
    # 2) 群消息事件 — 兼容 v2(header.event_type) 和 v1(type/event_type)
    header = body.get("header", {})
    event_type = header.get("event_type") or body.get("type") or body.get("event_type") or ""
    print(f"[FEISHU_WEBHOOK] event_type={event_type!r}", flush=True)
    if event_type != "im.message.receive_v1":
        return {"ok": True, "detail": f"忽略事件: {event_type}"}
    event = body.get("event", {})
    message = event.get("message", {})
    content_str = message.get("content", "{}")
    msg_type = message.get("msg_type", "")
    print(f"[FEISHU_WEBHOOK] msg_type={msg_type!r} content_str={content_str[:500]!r}", flush=True)
    try:
        content = json.loads(content_str)
    except (json.JSONDecodeError, TypeError):
        content = {}
    text = content.get("text", "")
    if not text:
        # Standard post format: {zh_cn: {title, content: [[{tag, text}, ...]]}}
        for lang_key in ("zh_cn", "en_us", "ja_jp", "ko_kr"):
            post = content.get(lang_key, {})
            if post:
                text = post.get("title", "") or ""
                for para in post.get("content", []):
                    for node in para:
                        if isinstance(node, dict) and node.get("tag") == "text":
                            text += node.get("text", "")
                if text:
                    break
    if not text:
        # Card/post format with top-level title + elements
        title = content.get("title", "")
        elements = content.get("elements", [])
        if title:
            text = title
        if elements:
            for block in elements:
                if isinstance(block, list):
                    for node in block:
                        if isinstance(node, dict) and node.get("tag") == "text":
                            text += node.get("text", "")
                elif isinstance(block, dict) and block.get("tag") == "text":
                    text += block.get("text", "")
        # Also check nested content (some card messages wrap text in data.content)
        if not text:
            data = content.get("data", {})
            if isinstance(data, dict):
                inner = data.get("content", {})
                if isinstance(inner, dict):
                    text = inner.get("content", "") or inner.get("text", "")
    if not text:
        # Last resort: check for any string value in content
        for v in content.values():
            if isinstance(v, str) and len(v) > 5:
                text = v
                break
    print(f"[FEISHU_WEBHOOK] extracted_text={text[:500]!r}", flush=True)
    if not text:
        return {"ok": True, "detail": "空消息"}
    settings = get_settings()
    # 按 app_id 路由到对应品牌租户
    app_id = header.get("app_id") or body.get("app_id", "")
    tenant_id = get_tenant_id_by_app_id(app_id) or settings.default_tenant_id
    client = get_feishu_client(tenant_id)
    try:
        with SessionLocal() as db:
            tenant = db.get(Tenant, tenant_id)
            industry_id = tenant.industry_id if tenant else None
            # 显式指令优先（回传/策略/托管），否则走 LLM 智能解析
            explicit_keywords = ("回传", "反馈", "策略", "托管")
            if any(kw in text for kw in explicit_keywords):
                reply = handle_feishu_command(text, db, tenant_id, industry_id, client)
            else:
                reply = process_feishu_message(
                    text=text,
                    sender=message.get("sender", {}).get("id", ""),
                    tenant_id=tenant_id,
                    industry_id=industry_id,
                )
        print(f"[FEISHU_WEBHOOK] reply={reply[:500]!r}", flush=True)
    except Exception as exc:
        print(f"[FEISHU_WEBHOOK] ERROR during processing: {exc}", flush=True)
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(exc)}
    # 回复到群
    try:
        # 回复功能已暂停（用户要求关闭）
        pass
    except Exception as exc:  # noqa: BLE001
        logger.exception("飞书回复失败: %s", exc)
    return {"ok": True, "reply": reply}


@router.get("/api/v1/feishu/daily-briefs")
def daily_briefs(_auth: dict = Depends(require_auth)) -> dict:
    """看板用：今日晨间任务清单 + 晚间运营日报 + 待执行任务列表。"""
    with SessionLocal() as db:
        return get_today_briefs(db, _auth["tenant"])


@router.post("/api/v1/feishu/trigger-brief")
def trigger_daily_brief(payload: BriefTriggerIn, _auth: dict = Depends(require_auth)) -> dict:
    """手动触发一次简报（测试/补发）。report_type: morning | evening。"""
    return trigger_brief(payload.report_type, _auth["tenant"])
