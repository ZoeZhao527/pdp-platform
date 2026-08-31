"""早九晚六定时简报：晨间任务清单 + 晚间运营日报。

晨间（9:00）：拉取今日待执行排期待办 → 按渠道分组 → 发飞书群 + 存库。
晚间（18:00）：聚合今日飞书采集的运营动作 → 生成日报 → 发飞书群 + 存库。
其他时间不触发任何发送，接收消息全程静默。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from logging import getLogger
from typing import Any

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.integrations.feishu import FeishuClient, get_feishu_client
from app.models import DailyReport, FeedbackEvent, StrategyTask

logger = getLogger(__name__)

# 渠道展示顺序与中文名映射
CHANNEL_ORDER = ["朋友圈", "社群", "1v1", "企微朋友圈", "企微1v1触达", "短信拉新", "销售"]
CHANNEL_LABELS = {
    "朋友圈": "朋友圈",
    "社群": "社群",
    "1v1": "1v1 触达",
    "企微朋友圈": "企微朋友圈",
    "企微1v1触达": "企微 1v1",
    "短信拉新": "短信拉新",
    "销售": "销售动作",
}

WEEKDAYS = "周一周二周三周四周五周六周日"


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _date_label() -> str:
    now = datetime.now()
    return f"{now.strftime('%m-%d')} {WEEKDAYS[now.weekday()]}"


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _channel_label(key: str) -> str:
    return CHANNEL_LABELS.get(key, key or "其他")


def _sort_channels(key: str) -> int:
    if key in CHANNEL_ORDER:
        return CHANNEL_ORDER.index(key)
    return len(CHANNEL_ORDER)


def run_morning_dispatch(
    db: Session,
    tenant_id: str,
    client: FeishuClient | None = None,
) -> dict[str, Any]:
    """9:00 晨间任务清单：今日待执行 → 分渠道 → 发群 + 存库。"""
    client = client or get_feishu_client(tenant_id)
    today = _today_str()
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    rows = (
        db.query(StrategyTask)
        .filter(StrategyTask.tenant_id == tenant_id)
        .filter(StrategyTask.status == "待安排")
        .filter(StrategyTask.due_at == today)
        .all()
    )
    todos = [r for r in rows if (r.result_json or {}).get("todo")]

    grouped: dict[str, list[StrategyTask]] = defaultdict(list)
    for t in todos:
        key = (t.result_json or {}).get("channel_key") or t.channel or "其他"
        grouped[_channel_label(key)].append(t)

    lines: list[str] = []
    lines.append(f"📋 今日运营任务清单 · {_date_label()}")
    lines.append("")

    if not todos:
        lines.append("今日暂无排期待办任务，可去指令中心生成月度计划。")
    else:
        for ch in sorted(grouped, key=_sort_channels):
            items = grouped[ch]
            items.sort(key=lambda x: (x.result_json or {}).get("due_time") or "99:99")
            lines.append(f"【{ch}】{len(items)} 条")
            for i, t in enumerate(items, 1):
                tm = (t.result_json or {}).get("due_time") or ""
                tm_part = f"⏰{tm} " if tm else ""
                lines.append(f"  {i}. {tm_part}{t.title}")
                # Include the actual script content so ops can use it directly
                script = (t.script or "").strip()
                if script:
                    lines.append(f"     ────────────────")
                    for script_line in script.split("\n"):
                        lines.append(f"     {script_line}")
                    lines.append(f"     ────────────────")
            lines.append("")
        lines.append(f"共 {len(todos)} 条任务，请按节奏执行。")

    content = "\n".join(lines)
    payload = {
        "task_count": len(todos),
        "channels": {ch: len(v) for ch, v in grouped.items()},
        "task_ids": [t.id for t in todos],
    }

    report = DailyReport(
        tenant_id=tenant_id,
        report_date=today,
        report_type="morning",
        content=content,
        payload_json=payload,
        sent=False,
    )
    db.add(report)
    db.commit()

    sent_ok = False
    send_err = ""
    try:
        res = client.send_message(content)
        sent_ok = bool(res.get("ok"))
    except Exception as exc:  # noqa: BLE001
        send_err = str(exc)
        logger.exception("晨间简报发送失败: %s", exc)

    report.sent = sent_ok
    report.sent_at = _now_ts() if sent_ok else None
    db.commit()
    return {"report_type": "morning", "task_count": len(todos), "sent": sent_ok, "error": send_err}


def run_evening_summary(
    db: Session,
    tenant_id: str,
    client: FeishuClient | None = None,
    _llm: bool = False,
) -> dict[str, Any]:
    """18:00 晚间运营日报：聚合今日采集动作 → 发群 + 存库。

    用 SQL 聚合而非 LLM，保证数据稳定可靠（本地小模型不适合做摘要）。
    """
    client = client or get_feishu_client(tenant_id)
    today = _today_str()
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    rows = (
        db.query(FeedbackEvent)
        .filter(FeedbackEvent.tenant_id == tenant_id)
        .filter(FeedbackEvent.created_at >= today_start)
        .all()
    )

    action_counts: dict[str, int] = defaultdict(int)
    action_amounts: dict[str, float] = defaultdict(float)
    notes: list[str] = []
    for r in rows:
        action = r.action or "其他"
        action_counts[action] += 1
        action_amounts[action] += r.amount or 0.0
        if r.note and len(notes) < 8:
            notes.append(r.note.replace("[飞书] ", "")[:60])

    lines: list[str] = []
    lines.append(f"📊 今日运营日报 · {_date_label()}")
    lines.append("")
    lines.append("【采集动态】")
    lines.append(f"  飞书回传 {len(rows)} 条")
    lines.append("")

    if action_counts:
        lines.append("【动作分布】")
        parts = [f"{a} {c} 次" for a, c in sorted(action_counts.items(), key=lambda x: -x[1])]
        lines.append("  " + " | ".join(parts))
        lines.append("")

    total_amount = sum(action_amounts.values())
    if total_amount > 0:
        lines.append("【关键数据】")
        amt_parts = [f"{a} {int(v)}" for a, v in action_amounts.items() if v > 0]
        lines.append("  " + " | ".join(amt_parts) + f"  · 累计 ¥{int(total_amount)}")
        lines.append("")

    if notes:
        lines.append("【动作摘要】")
        for n in notes:
            lines.append(f"  · {n}")
        lines.append("")

    # 任务执行缺口：今日待安排但已过点
    pending = (
        db.query(StrategyTask)
        .filter(StrategyTask.tenant_id == tenant_id)
        .filter(StrategyTask.status == "待安排")
        .filter(StrategyTask.due_at == today)
        .all()
    )
    pending_todos = [t for t in pending if (t.result_json or {}).get("todo")]
    if pending_todos:
        lines.append("【待跟进】")
        lines.append(f"  {len(pending_todos)} 条任务未执行，请跟进闭环")
        lines.append("")

    lines.append("明日建议：根据今日动作分布调整触达节奏与卡项侧重。")
    content = "\n".join(lines)

    payload = {
        "feedback_count": len(rows),
        "action_breakdown": dict(action_counts),
        "total_amount": total_amount,
        "pending_tasks": len(pending_todos),
    }

    report = DailyReport(
        tenant_id=tenant_id,
        report_date=today,
        report_type="evening",
        content=content,
        payload_json=payload,
        sent=False,
    )
    db.add(report)
    db.commit()

    sent_ok = False
    send_err = ""
    try:
        res = client.send_message(content)
        sent_ok = bool(res.get("ok"))
    except Exception as exc:  # noqa: BLE001
        send_err = str(exc)
        logger.exception("晚间日报发送失败: %s", exc)

    report.sent = sent_ok
    report.sent_at = _now_ts() if sent_ok else None
    db.commit()
    return {"report_type": "evening", "feedback_count": len(rows), "sent": sent_ok, "error": send_err}


def get_today_briefs(db: Session, tenant_id: str) -> dict[str, Any]:
    """看板用：取今日最新晨间/晚间简报。"""
    today = _today_str()
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    result: dict[str, Any] = {"morning": None, "evening": None, "pending_tasks": []}
    for rtype in ("morning", "evening"):
        row = (
            db.query(DailyReport)
            .filter(DailyReport.tenant_id == tenant_id)
            .filter(DailyReport.report_date == today)
            .filter(DailyReport.report_type == rtype)
            .order_by(DailyReport.created_at.desc())
            .first()
        )
        if row:
            result[rtype] = {
                "content": row.content,
                "sent": row.sent,
                "sent_at": row.sent_at,
                "payload": row.payload_json,
            }

    today_str = today
    pending = (
        db.query(StrategyTask)
        .filter(StrategyTask.tenant_id == tenant_id)
        .filter(StrategyTask.status == "待安排")
        .filter(StrategyTask.due_at == today_str)
        .all()
    )
    result["pending_tasks"] = [
        {
            "id": t.id,
            "title": t.title,
            "channel": _channel_label((t.result_json or {}).get("channel_key") or t.channel or "其他"),
            "due_time": (t.result_json or {}).get("due_time") or "",
            "audience": t.audience or "",
        }
        for t in pending
        if (t.result_json or {}).get("todo")
    ]
    return result


def trigger_brief(report_type: str, tenant_id: str) -> dict[str, Any]:
    """手动触发一次简报（测试/补发用），独立开 session。"""
    with SessionLocal() as db:
        if report_type == "morning":
            return run_morning_dispatch(db, tenant_id)
        if report_type == "evening":
            return run_evening_summary(db, tenant_id)
    return {"error": "unknown report_type"}
