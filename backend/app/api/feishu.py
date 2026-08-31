"""飞书接口路由：拉消息 / 发消息 / 指令处理 / webhook 回调。

前三个接口需要登录鉴权；/webhook/feishu 公开，供飞书事件订阅回调。
"""

from __future__ import annotations

import json
from logging import getLogger
from typing import Any
from datetime import date

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.auth import require_auth
from app.api.deps import get_tenant_id
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
def feishu_config(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """返回当前租户的飞书配置（app_secret 脱敏显示）。"""
    with SessionLocal() as db:
        cfg = db.query(FeishuConfig).filter(FeishuConfig.tenant_id == tenant_id).first()
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
def update_feishu_config(payload: FeishuConfigIn, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """保存或更新当前租户的飞书配置。"""
    tenant_id = tenant_id
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
def feishu_test(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """测试飞书连接：获取 tenant_access_token。"""
    client = get_feishu_client(tenant_id)
    if not client.app_id or not client.app_secret:
        return {"ok": False, "detail": "请先填写 App ID 和 App Secret"}
    try:
        token = client._get_tenant_access_token()
        return {"ok": True, "detail": f"连接成功，token 前 8 位: {token[:8]}..."}
    except Exception as exc:
        return {"ok": False, "detail": f"连接失败: {exc}"}


@router.get("/api/v1/feishu/messages")
def feishu_messages(limit: int = 20, tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    client = get_feishu_client(tenant_id)
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
def feishu_send(payload: FeishuSendIn, tenant_id: str = Depends(get_tenant_id)) -> dict:
    client = get_feishu_client(tenant_id)
    return client.send_message(payload.text)


@router.post("/api/v1/feishu/handle")
def feishu_handle(payload: FeishuHandleIn, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with SessionLocal() as db:
        tenant = db.get(Tenant, tenant_id)
        industry_id = tenant.industry_id if tenant else None
        reply = handle_feishu_command(payload.text, db, tenant_id, industry_id)
    return {"reply": reply}


@router.get("/api/v1/feishu/summary")
def feishu_summary(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """今日飞书回传统计：消息数、解析数、操作类型分布、KPI更新数。"""
    from datetime import datetime
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    with SessionLocal() as db:
        # Count feedback events from Feishu today
        rows = (
            db.query(FeedbackEvent)
            .filter(FeedbackEvent.tenant_id == tenant_id)
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
                # 3.0: 自动检测策略执行情况回复格式（序号 | 发布 | 触达 | 成交）
                import re as _re
                if _re.search(r'\d+\s*[|｜]\s*\S+', text):
                    parsed = parse_execution_reply(text)
                    if parsed:
                        from app.models import StrategyTask, FeedbackEvent
                        from app.api.platform import _log_run
                        tasks_q = db.query(StrategyTask).filter(
                            StrategyTask.tenant_id == tenant_id,
                            StrategyTask.status.in_(["待执行", "执行中"]),
                        ).order_by(StrategyTask.created_at.desc()).limit(20).all()
                        for item in parsed:
                            seq = item["seq"]
                            if 1 <= seq <= len(tasks_q):
                                task = tasks_q[seq - 1]
                                db.add(FeedbackEvent(
                                    tenant_id=tenant_id,
                                    task_id=task.id,
                                    action=item["published"],
                                    amount=item["amount"],
                                    note=f"触达{item['touched']}人 | {item['note']}",
                                    occurred_at=date.today().isoformat(),
                                ))
                                if "已发布" in item["published"] or "已执行" in item["published"]:
                                    task.status = "已完成"
                                _log_run(db, tenant_id, "feishu", "feedback_collected",
                                          instruction_id=task.instruction_id,
                                          detail=f"自动解析: 任务{seq}, {item['published']}, 触达{item['touched']}, 成交{item['amount']}",
                                          operator="飞书群自动",
                                          extra=item)
                        db.commit()
                        reply = f"已收录 {len(parsed)} 条执行反馈，已回传到系统策略执行记录。"
                    else:
                        reply = process_feishu_message(text=text, sender=message.get("sender", {}).get("id", ""), tenant_id=tenant_id, industry_id=industry_id)
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
def daily_briefs(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """看板用：今日晨间任务清单 + 晚间运营日报 + 待执行任务列表。"""
    with SessionLocal() as db:
        return get_today_briefs(db, tenant_id)


@router.post("/api/v1/feishu/trigger-brief")
def trigger_daily_brief(payload: BriefTriggerIn, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """手动触发一次简报（测试/补发）。report_type: morning | evening。"""
    return trigger_brief(payload.report_type, tenant_id)


# ---------------------------------------------------------------------------
# 3.0 P2: 飞书策略回传闭环
# ---------------------------------------------------------------------------
# 目标：早上下发策略后，18:00 发一条结构化收集消息到群，
# 运营回复执行情况（发布/触达/成交），系统解析后回传到策略执行记录。
# 注意：用户要求飞书不发消息，以下只构建能力，不实际发送。
# ---------------------------------------------------------------------------


class ExecutionCollectIn(BaseModel):
    instruction_id: str = ""
    dry_run: bool = True  # 默认 dry_run=True，不实际发送


def build_execution_collection_message(db, tenant_id: str, instruction_id: str = "") -> str:
    """构建 18:00 策略执行情况收集消息文本。

    读取今天下发的策略任务，生成结构化收集模板。
    运营按格式回复，系统自动解析回传。
    """
    from app.models import StrategyTask, Instruction
    from datetime import date, datetime

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    q = db.query(StrategyTask).filter(
        StrategyTask.tenant_id == tenant_id,
        StrategyTask.status.in_(["待执行", "执行中"]),
    )
    if instruction_id:
        q = q.filter(StrategyTask.instruction_id == instruction_id)
    tasks = q.order_by(StrategyTask.created_at.desc()).limit(20).all()

    if not tasks:
        return "📋 今日暂无待收集执行数据的策略任务。"

    lines = ["📋 【策略执行情况收集】", f"日期：{today}", ""]
    lines.append("请各位运营回复今日策略执行情况，格式如下：")
    lines.append("")
    lines.append("格式：任务序号 | 发布情况 | 触达人数 | 成交金额 | 备注")
    lines.append("示例：1 | 已发布朋友圈3条 | 触达320人 | 成交5800元 | 客户反馈不错")
    lines.append("")
    lines.append("---")
    for i, task in enumerate(tasks, 1):
        ch = task.channel or "-"
        title = task.title or "-"
        lines.append(f"{i}. [{ch}] {title}")
    lines.append("---")
    lines.append("")
    lines.append("回复示例：1 | 已发布 | 280人 | 3500元 | 转化率1.2%")
    return "\n".join(lines)


def parse_execution_reply(text: str) -> list[dict]:
    """解析运营回复的执行情况，提取结构化数据。

    支持格式：序号 | 发布情况 | 触达人数 | 成交金额 | 备注
    也支持自然语言中的数字提取。
    """
    import re
    results: list[dict] = []

    # Pattern: "1 | 已发布 | 320人 | 5800元 | 备注..."
    pattern = r'(\d+)\s*[|｜]\s*([^|｜]+?)(?:\s*[|｜]\s*([^|｜]+?))?(?:\s*[|｜]\s*([^|｜]+?))?(?:\s*[|｜]\s*(.+))?'
    for match in re.finditer(pattern, text):
        seq = int(match.group(1))
        published = (match.group(2) or "").strip()
        touched_raw = (match.group(3) or "").strip()
        amount_raw = (match.group(4) or "").strip()
        note = (match.group(5) or "").strip()

        touched = 0
        m = re.search(r'(\d+)', touched_raw)
        if m:
            touched = int(m.group(1))

        amount = 0.0
        m = re.search(r'(\d+(?:\.\d+)?)', amount_raw)
        if m:
            amount = float(m.group(1))

        results.append({
            "seq": seq,
            "published": published,
            "touched": touched,
            "amount": amount,
            "note": note,
        })

    return results


@router.post("/api/v1/feishu/collect-execution")
def collect_execution_feedback(
    payload: ExecutionCollectIn,
    tenant_id: str = Depends(get_tenant_id),
) -> dict:
    """生成策略执行收集消息。

    dry_run=True（默认）：只返回消息文本，不发送到飞书群。
    dry_run=False：发送到飞书群（需要用户明确说可以发才用）。
    """
    with SessionLocal() as db:
        msg_text = build_execution_collection_message(db, tenant_id, payload.instruction_id)

    if not payload.dry_run:
        client = get_feishu_client(tenant_id)
        send_result = client.send_message(msg_text)
        return {"ok": True, "message": msg_text, "send_result": send_result, "sent": True}

    return {"ok": True, "message": msg_text, "sent": False, "note": "dry_run 模式，未发送到飞书群"}


@router.post("/api/v1/feishu/parse-feedback")
def parse_feedback(payload: FeishuHandleIn, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """手动解析一段飞书群回复文本，提取执行数据并回传到系统。

    用于测试/验证解析逻辑，或手动录入运营反馈。
    """
    with SessionLocal() as db:
        parsed = parse_execution_reply(payload.text)
        # Write parsed feedback to FeedbackEvent + system runlog
        from app.models import StrategyTask, FeedbackEvent
        from app.api.platform import _log_run

        tasks_q = db.query(StrategyTask).filter(
            StrategyTask.tenant_id == tenant_id,
            StrategyTask.status.in_(["待执行", "执行中"]),
        ).order_by(StrategyTask.created_at.desc()).limit(20).all()

        saved = 0
        for item in parsed:
            seq = item["seq"]
            if seq < 1 or seq > len(tasks_q):
                continue
            task = tasks_q[seq - 1]
            # Write FeedbackEvent
            fb = FeedbackEvent(
                tenant_id=tenant_id,
                task_id=task.id,
                action=item["published"],
                amount=item["amount"],
                note=f"触达{item['touched']}人 | {item['note']}",
                occurred_at=date.today().isoformat(),
            )
            db.add(fb)
            # Update task status
            if "已发布" in item["published"] or "已执行" in item["published"]:
                task.status = "已完成"
            # Log to system runlog
            _log_run(db, tenant_id, "feishu", "feedback_collected",
                      instruction_id=task.instruction_id,
                      detail=f"任务{seq}: {item['published']}, 触达{item['touched']}, 成交{item['amount']}元",
                      operator="运营",
                      extra=item)
            saved += 1

        db.commit()
        return {"ok": True, "parsed": parsed, "saved": saved}
