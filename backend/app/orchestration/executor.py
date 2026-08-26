"""审批后的全链路自动执行：拆渠道任务、护栏校验、触达发送、跟进与验收清单。"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.channels.gateway import channel_gateway
from app.guardrails.service import GuardrailService
from app.models import (
    Alert,
    FeedbackEvent,
    Instruction,
    Strategy,
    StrategyTask,
    Tenant,
)


PLAN_WINDOW_DAYS = 30
WEEKDAY_INDEX = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
DEFAULT_SEND_POLICY = {
    "auto_enabled": True,
    "window_start": "09:00",
    "window_end": "21:00",
    "grace_hours": 24,
    "max_per_day": {},
    "paused_channels": [],
}


def _short_channel(channel: str) -> str:
    if "朋友圈" in channel:
        return "朋友圈"
    if "社群" in channel:
        return "社群"
    if "公众号" in channel:
        return "公众号"
    if "1v1" in channel or "私信" in channel:
        return "1v1"
    if "短信" in channel:
        return "短信"
    if "跟进" in channel:
        return "跟进"
    return channel


def _due_time_from_slots(time_slots: str) -> str:
    import re

    match = re.search(r"(\d{1,2}:\d{2})", time_slots or "")
    return match.group(1) if match else ""


def _plan_dates_for_schedule(schedule: dict, start: datetime, days: int) -> list[str]:
    cadence = schedule.get("cadence") or ""
    time_slots = schedule.get("time_slots") or ""
    if "每日" in cadence or "每天" in cadence:
        return [(start + timedelta(days=offset)).strftime("%Y-%m-%d") for offset in range(days)]
    if "每周" in cadence:
        import re

        weekdays = [WEEKDAY_INDEX[name] for name in re.findall(r"周([一二三四五六日天])", time_slots)]
        if not weekdays:
            return []
        result: list[str] = []
        for offset in range(days):
            date = start + timedelta(days=offset)
            if date.weekday() in weekdays:
                result.append(date.strftime("%Y-%m-%d"))
        return result
    if "按节点" in cadence or "节点" in cadence:
        import re

        offsets = [int(value) for value in re.findall(r"T\+(\d+)", time_slots)]
        if not offsets:
            return []
        return [
            (start + timedelta(days=offset)).strftime("%Y-%m-%d")
            for offset in offsets
            if offset < days
        ]
    return []


def _date_from_day_string(day_str: str, start: datetime) -> str | None:
    """Parse '第1天'/'Day 1'/'第3天' style strings and return a date string, or None."""
    import re

    match = re.search(r"第?\s*(\d+)\s*天", day_str)
    if not match:
        match = re.search(r"[Dd]ay\s*(\d+)", day_str)
    if not match:
        return None
    day_num = int(match.group(1))
    offset = max(day_num - 1, 0)
    return (start + timedelta(days=offset)).strftime("%Y-%m-%d")


def _build_daily_content_lookup(daily_content: list) -> dict:
    """Build {(day_offset, channel_short): content} from daily_content list."""
    lookup: dict[tuple[int, str], str] = {}
    for dc in daily_content:
        day_str = dc.get("day") or ""
        match = re.search(r"第?\s*(\d+)\s*天", day_str)
        if not match:
            match = re.search(r"[Dd]ay\s*(\d+)", day_str)
        if not match:
            continue
        day_offset = max(int(match.group(1)) - 1, 0)
        channel = _short_channel(dc.get("channel") or "朋友圈")
        content = dc.get("content") or ""
        if content:
            lookup[(day_offset, channel)] = content
    return lookup


def _sales_playbook_for_channel(asset: dict, channel_key: str) -> str:
    """Pull relevant sales playbook text for a channel (1v1 gets the richest)."""
    sp = asset.get("sales_playbook") or {}
    parts: list[str] = []
    # Layer plays for 1v1
    if channel_key == "1v1":
        for lp in sp.get("layer_plays", []) or []:
            layer = lp.get("layer", "")
            script = lp.get("script", "")
            action = lp.get("action", "")
            if script:
                parts.append(f"【{layer}·{action}】\n{script}")
        # Objections (top 3)
        for ob in (sp.get("objections", []) or [])[:3]:
            issue = ob.get("issue", "")
            resp = ob.get("response", "")
            if issue and resp:
                parts.append(f"异议：{issue}\n回应：{resp}")
    # Sections for all channels
    for sec in sp.get("sections", []) or []:
        if isinstance(sec, str) and len(sec) > 20:
            parts.append(sec)
        elif isinstance(sec, dict):
            label = sec.get("label") or sec.get("title") or ""
            text = sec.get("content") or sec.get("script") or ""
            if text:
                parts.append(f"【{label}】\n{text}" if label else text)
    return "\n\n".join(parts)


def materialize_plan_todos(db: Session, instruction: Instruction, days: int = PLAN_WINDOW_DAYS) -> int:
    """把资产包内容排期展开成可编辑的待办任务（待安排，不自动执行）。"""
    asset = instruction.asset_json or {}
    content_schedule = asset.get("content_schedule", {}) or {}
    schedules = content_schedule.get("schedules", []) or []
    materials = content_schedule.get("materials", []) or []
    if not schedules:
        # Fallback: build plan todos from daily_content when schedules is empty
        daily_content = content_schedule.get("daily_content", []) or []
        if daily_content:
            start = datetime.now()
            created = 0
            for dc in daily_content:
                due_date = _date_from_day_string(dc.get("day") or "", start)
                if not due_date:
                    due_date = (start + timedelta(days=created % max(days, 1))).strftime("%Y-%m-%d")
                content = dc.get("content") or ""
                channel = dc.get("channel") or "朋友圈"
                db.add(
                    StrategyTask(
                        tenant_id=instruction.tenant_id,
                        industry_id=instruction.industry_id,
                        instruction_id=instruction.id,
                        title=f"{instruction.title}·{channel}",
                        channel=channel,
                        script=content,
                        acceptance="待安排",
                        status="待安排",
                        due_at=due_date,
                        result_json={
                            "todo": True,
                            "channel_key": _short_channel(channel),
                            "due_time": "12:00",
                            "plan_series": created,
                            "daily_content_index": created,
                        },
                    )
                )
                created += 1
            db.commit()
            return created
        return 0
    # Build rich-content lookup from daily_content
    daily_content = content_schedule.get("daily_content", []) or []
    dc_lookup = _build_daily_content_lookup(daily_content)
    dc_day_count = max(
        (k[0] for k in dc_lookup.keys()), default=-1,
    ) + 1 or 1

    start = datetime.now()
    start_date = start.replace(hour=0, minute=0, second=0, microsecond=0)
    created = 0
    for schedule_index, schedule in enumerate(schedules):
        schedule_channel = _short_channel(schedule.get("channel") or "")
        for due_date in _plan_dates_for_schedule(schedule, start, days):
            # Calculate day offset for daily_content lookup
            try:
                due_dt = datetime.strptime(due_date, "%Y-%m-%d")
                day_offset = (due_dt - start_date).days
            except ValueError:
                day_offset = created
            # Cycle through available daily_content days
            cycled_offset = day_offset % dc_day_count if dc_day_count > 0 else 0
            content = dc_lookup.get((cycled_offset, schedule_channel), "")
            content_source = "daily_content" if content else ""
            # Fall back to materials copy
            if not content:
                material = next(
                    (item for item in materials if item.get("channel") == schedule.get("channel")),
                    materials[0] if materials else None,
                )
                content = material.get("copy") if material else ""
                content_source = "materials" if content else ""
            content = content or schedule.get("goal") or ""
            # Enrich 1v1 with sales playbook
            playbook = ""
            if schedule_channel == "1v1":
                playbook = _sales_playbook_for_channel(asset, schedule_channel)
                if playbook and content:
                    content = content + "\n\n--- 销售话术参考 ---\n" + playbook
                elif playbook:
                    content = playbook
                    content_source = "sales_playbook"
            db.add(
                StrategyTask(
                    tenant_id=instruction.tenant_id,
                    industry_id=instruction.industry_id,
                    instruction_id=instruction.id,
                    title=f"{instruction.title}·{schedule.get('content_type') or schedule.get('channel')}",
                    channel=schedule.get("channel") or "",
                    script=content,
                    acceptance="待安排",
                    status="待安排",
                    due_at=due_date,
                    result_json={
                        "todo": True,
                        "channel_key": schedule_channel,
                        "due_time": _due_time_from_slots(schedule.get("time_slots") or ""),
                        "plan_series": schedule_index,
                        "content_source": content_source,
                        "day_offset": day_offset,
                    },
                )
            )
            created += 1
    db.commit()
    return created


def rebuild_plan_todos(db: Session, instruction: Instruction, days: int = PLAN_WINDOW_DAYS) -> int:
    """删除旧待办并按当前内容模板重算。"""
    db.query(StrategyTask).filter(
        StrategyTask.instruction_id == instruction.id,
        StrategyTask.status == "待安排",
    ).delete(synchronize_session=False)
    db.commit()
    return materialize_plan_todos(db, instruction, days)


def materialize_strategy_plan_todos(db: Session, strategy: Strategy, days: int = PLAN_WINDOW_DAYS) -> int:
    """把托管策略展开成 30 天可编辑待办，进入统一调度器自动下发。"""
    params = strategy.params_json or {}
    channels = [item.strip() for item in re.split(r"[、,，;；/|]", params.get("channels") or "") if item.strip()]
    if not channels:
        channels = ["朋友圈"]
    cadence = params.get("cadence") or ""
    daily = "每日" in cadence or "每天" in cadence
    time_slots = params.get("time_slots") or ("12:00 / 20:00" if daily else "周一/三/五 19:30")

    db.query(StrategyTask).filter(
        StrategyTask.strategy_id == strategy.id,
        StrategyTask.status == "待安排",
    ).delete(synchronize_session=False)
    db.commit()

    start = datetime.now()
    created = 0
    for channel in channels:
        if daily:
            dates = [(start + timedelta(days=offset)).strftime("%Y-%m-%d") for offset in range(days)]
        else:
            weekdays = [WEEKDAY_INDEX[name] for name in re.findall(r"周([一二三四五六日天])", time_slots)]
            weekdays = weekdays or [0, 2, 4]
            dates = []
            for offset in range(days):
                date = start + timedelta(days=offset)
                if date.weekday() in weekdays:
                    dates.append(date.strftime("%Y-%m-%d"))
        for due_date in dates:
            db.add(
                StrategyTask(
                    tenant_id=strategy.tenant_id,
                    industry_id=strategy.industry_id,
                    strategy_id=strategy.id,
                    title=f"{strategy.name}·{channel}",
                    channel=channel,
                    script=params.get("script") or f"{strategy.name}·{channel} 自动执行内容",
                    acceptance=params.get("acceptance") or "自动验收",
                    status="待安排",
                    due_at=due_date,
                    result_json={
                        "todo": True,
                        "channel_key": _short_channel(channel),
                        "due_time": _due_time_from_slots(time_slots),
                        "strategy_plan": True,
                    },
                )
            )
            created += 1
    db.commit()
    return created


def update_plan_todo(db: Session, task_id: str, payload: dict) -> StrategyTask | None:
    task = db.get(StrategyTask, task_id)
    if task is None or not (task.result_json or {}).get("todo"):
        return None
    result = dict(task.result_json or {})
    if payload.get("due_at"):
        task.due_at = payload["due_at"]
    if payload.get("due_time") is not None:
        result["due_time"] = payload["due_time"]
    if payload.get("content") is not None:
        task.script = payload["content"]
    if payload.get("status"):
        task.status = payload["status"]
    task.result_json = result
    db.commit()
    db.refresh(task)
    return task


def _due_datetime(task: StrategyTask) -> datetime:
    result = task.result_json or {}
    date_part = task.due_at or datetime.now().strftime("%Y-%m-%d")
    time_part = result.get("due_time") or "09:00"
    try:
        return datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M")
    except ValueError:
        return datetime.now()


def load_send_policy(db: Session, tenant_id: str) -> dict:
    tenant = db.get(Tenant, tenant_id)
    config = dict(tenant.config_json or {}) if tenant else {}
    policy = dict(DEFAULT_SEND_POLICY)
    policy.update(config.get("send_policy") or {})
    return policy


def _parse_time(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%H:%M")
    except (TypeError, ValueError):
        return datetime.strptime("09:00", "%H:%M")


def _next_allowed_datetime(due: datetime, window_start: str, window_end: str) -> datetime:
    start = _parse_time(window_start)
    end = _parse_time(window_end)
    if due.time() < start.time():
        return due.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)
    if due.time() > end.time():
        next_day = due + timedelta(days=1)
        return next_day.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)
    return due


def dispatch_due_plan_todos(
    db: Session,
    tenant_id: str,
    now: datetime | None = None,
    grace_hours: int = 24,
    policy: dict | None = None,
) -> dict:
    """到点自动下发排期待办；超过补发窗口的标记为已错过。"""
    now = now or datetime.now()
    policy = policy or load_send_policy(db, tenant_id)
    if not policy.get("auto_enabled", True):
        return {"dispatched": 0, "missed": 0, "skipped": 0, "paused": 0, "frequency_capped": 0, "reason": "auto_disabled"}
    grace_hours = grace_hours if grace_hours is not None else int(policy.get("grace_hours") or 24)

    paused_instruction_ids: set[str] = set()
    for instruction in db.query(Instruction).filter(Instruction.tenant_id == tenant_id).all():
        if (instruction.strategy_ids_json or {}).get("plan_paused"):
            paused_instruction_ids.add(instruction.id)
    paused_channels = set(policy.get("paused_channels") or [])
    max_per_day = policy.get("max_per_day") or {}
    today = now.strftime("%Y-%m-%d")
    dispatched_today: dict[str, int] = {}
    for task in db.query(StrategyTask).filter(
        StrategyTask.tenant_id == tenant_id,
        StrategyTask.status.in_(["已完成", "已拦截"]),
        StrategyTask.due_at == today,
    ).all():
        if (task.result_json or {}).get("todo"):
            key = _channel_key(task)
            dispatched_today[key] = dispatched_today.get(key, 0) + 1

    todos = (
        db.query(StrategyTask)
        .filter(
            StrategyTask.tenant_id == tenant_id,
            StrategyTask.status == "待安排",
        )
        .all()
    )
    dispatched = 0
    missed = 0
    paused = 0
    frequency_capped = 0
    for task in todos:
        if not (task.result_json or {}).get("todo"):
            continue
        channel_key = _channel_key(task)
        if (
            (task.instruction_id and task.instruction_id in paused_instruction_ids)
            or channel_key in paused_channels
        ):
            paused += 1
            continue
        due = _due_datetime(task)
        allowed = _next_allowed_datetime(
            due,
            policy.get("window_start"),
            policy.get("window_end"),
        )
        if now < allowed:
            continue
        if now - allowed > timedelta(hours=grace_hours):
            result = dict(task.result_json or {})
            result["missed"] = True
            task.result_json = result
            task.status = "已错过"
            db.add(
                Alert(
                    tenant_id=task.tenant_id,
                    task_id=task.id,
                    alert_type="漏发提醒",
                    message=f"{task.title} 已超过补发窗口，请人工处理",
                )
            )
            db.commit()
            missed += 1
            continue
        limit = int(max_per_day.get(channel_key, 0) or 0)
        if limit and dispatched_today.get(channel_key, 0) >= limit:
            result = dict(task.result_json or {})
            result["frequency_capped"] = True
            task.result_json = result
            task.status = "已跳过"
            db.add(
                Alert(
                    tenant_id=task.tenant_id,
                    task_id=task.id,
                    alert_type="频率限制",
                    message=f"{task.title} 超过当日 {channel_key} 发送上限，已跳过",
                )
            )
            db.commit()
            frequency_capped += 1
            continue
        execute_channel_task(db, task)
        dispatched_today[channel_key] = dispatched_today.get(channel_key, 0) + 1
        dispatched += 1
    return {
        "dispatched": dispatched,
        "missed": missed,
        "paused": paused,
        "frequency_capped": frequency_capped,
    }


def _short(text: str, limit: int = 220) -> str:
    text = (text or "").strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def _channel_key(task: StrategyTask) -> str:
    return (task.result_json or {}).get("channel_key") or "1v1"


def _children_of(db: Session, instruction: Instruction) -> list[StrategyTask]:
    tasks = (
        db.query(StrategyTask)
        .filter(StrategyTask.instruction_id == instruction.id)
        .order_by(StrategyTask.created_at.asc())
        .all()
    )
    parent_id = (instruction.strategy_ids_json or {}).get("parent_task_id")
    if parent_id:
        return [
            task
            for task in tasks
            if task.id != parent_id and not (task.result_json or {}).get("todo")
        ]
    return [
        task
        for task in tasks
        if (task.result_json or {}).get("child") and not (task.result_json or {}).get("todo")
    ]


def _compose_channel_content(channel_key: str, asset: dict) -> str:
    activity = asset.get("activity_plan", {})
    activity_details = asset.get("activity_details", {})
    card = asset.get("card_structure", {})
    scripts = asset.get("script_templates", {})
    theme = activity.get("theme") or ""
    goal = activity.get("goal") or ""
    summary = activity_details.get("summary") or ""
    calendar = activity_details.get("calendar") or ""
    card_items = card.get("items") or []
    if card_items:
        card_summary = "；".join(
            f"{item.get('name', '')}({item.get('price', '')}元，{item.get('role', '')})"
            for item in card_items[:5]
        )
    else:
        card_summary = card.get("summary") or ""
    card_rules = card.get("rules") or ""
    opening = scripts.get("opening") or ""
    closing = scripts.get("close") or ""
    objection_handling = scripts.get("objection_handling") or []
    if objection_handling:
        objection = "；".join(
            f"{item.get('scenario', '')}→{item.get('response', '')}"
            for item in objection_handling[:3]
        )
    else:
        objection = scripts.get("objection") or ""
    follow_up = scripts.get("follow_up") or ""
    content_schedule = asset.get("content_schedule", {})
    daily_content = content_schedule.get("daily_content") or []

    if channel_key == "1v1":
        parts = [
            f"【1v1 触达】活动：{theme}（目标 {goal or '待确认'}）",
            f"卡项卖点：{_short(card_summary, 400)}",
        ]
        layered = scripts.get("layered_scripts") or []
        for ls in layered:
            parts.append(f"\n【{ls.get('layer', '')}】开场：{_short(ls.get('opening', ''), 300)}")
            parts.append(f"逼单：{_short(ls.get('close', ''), 300)}")
            parts.append(f"回访：{_short(ls.get('follow_up', ''), 300)}")
        if objection_handling:
            parts.append("\n【异议处理】")
            for item in objection_handling[:8]:
                cat = item.get("category", "")
                parts.append(f"[{cat}] {item.get('scenario', '')}→{_short(item.get('response', ''), 300)}")
        return "\n\n".join(p for p in parts if p)
    if channel_key == "朋友圈":
        if daily_content:
            moments = [d for d in daily_content if "朋友圈" in (d.get("channel") or "")]
            if moments:
                return "\n\n".join(
                    f"【朋友圈 {d.get('day', '')}】{d.get('content', '')}"
                    for d in moments
                )
        day1 = f"【朋友圈 Day1】{_short(theme, 60)}正式启动，{_short(summary, 180)}"
        day2 = f"【朋友圈 Day2】真实卡项种草：{_short(card_summary, 180)}"
        day3 = f"【朋友圈 Day3】老客回访：{_short(follow_up, 180)}"
        return "\n\n".join([day1, day2, day3])
    if channel_key == "社群":
        if daily_content:
            group_msgs = [d for d in daily_content if "社群" in (d.get("channel") or "")]
            if group_msgs:
                return "\n\n".join(
                    f"【社群 {d.get('day', '')}】{d.get('content', '')}"
                    for d in group_msgs
                )
        return "\n".join(
            [
                f"【社群活动宣发】{theme}",
                f"目标：{goal or '待确认'}",
                f"活动要点：{summary}",
                f"执行日历：{calendar}",
            ]
        )
    if channel_key == "短信":
        return f"【短信拉新】{_short(theme, 40)}已开启，{_short(summary, 120)} 回复 1 领取福利 [短链] 拒收请回R"
    if channel_key == "跟进":
        return f"【自动跟进】{_short(follow_up, 260)} 若客户已回复，请按 {_short(closing, 120)} 推进成交"
    return theme


def plan_execution_tasks(
    db: Session,
    instruction: Instruction,
    parent_task: StrategyTask,
    asset: dict,
    params: dict,
) -> list[StrategyTask]:
    """把已批准的资产包拆成渠道执行任务并自动入队。"""
    today = datetime.now()
    channel_specs = [
        ("1v1", "企微1v1触达", 0),
        ("朋友圈", "企微朋友圈", 0),
        ("社群", "企微社群", 1),
        ("短信", "短信拉新", 0),
        ("跟进", "企微跟进回访", 3),
    ]
    children: list[StrategyTask] = []
    plan: list[dict] = []
    for key, title, offset_days in channel_specs:
        content = _compose_channel_content(key, asset)
        due = (today + timedelta(days=offset_days)).strftime("%Y-%m-%d")
        plan.append({"channel_key": key, "title": title, "due_at": due})
        task = StrategyTask(
            tenant_id=instruction.tenant_id,
            industry_id=instruction.industry_id,
            instruction_id=instruction.id,
            strategy_id=parent_task.strategy_id,
            title=f"{instruction.title}·{title}",
            channel=title,
            script=content,
            acceptance="自动执行",
            status="待执行",
            due_at=due,
            result_json={"child": True, "channel_key": key},
        )
        db.add(task)
        children.append(task)
    parent_task.status = "执行中"
    parent_task.result_json = {
        "reply": parent_task.script,
        "asset": asset,
        "plan": plan,
    }
    strategy_ids = dict(instruction.strategy_ids_json or {})
    strategy_ids["parent_task_id"] = parent_task.id
    instruction.strategy_ids_json = strategy_ids
    db.commit()
    for task in children:
        db.refresh(task)
    return children


def _mark_blocked(db: Session, task: StrategyTask, rule_name: str, note: str) -> None:
    task.status = "已拦截"
    result = dict(task.result_json or {})
    result["guardrail"] = {"matched_rule": rule_name, "note": note}
    task.result_json = result
    db.add(
        Alert(
            tenant_id=task.tenant_id,
            task_id=task.id,
            alert_type="合规拦截",
            message=f"{task.title} 命中 {rule_name}：{note}",
        )
    )


def execute_channel_task(db: Session, task: StrategyTask) -> dict:
    """执行单条渠道任务：护栏校验 -> 渠道发送 -> 结果记录 -> 验收刷新。"""
    task.status = "执行中"
    db.commit()
    result: dict = dict(task.result_json or {})
    result["channel"] = task.channel
    result["content"] = _short(task.script or task.title, 400)

    guardrail = GuardrailService(db).check(task.tenant_id, task.script or task.title)
    if not guardrail.passed:
        _mark_blocked(db, task, guardrail.matched_rule or "护栏", guardrail.note or "")
        db.commit()
        return {"status": task.status, "reason": guardrail.note}

    channel_type = "mock"
    send = channel_gateway.send(
        channel_type,
        task.id,
        task.id,
        task.script or task.title,
        {"channel_key": _channel_key(task)},
    )
    result["message_id"] = send.message_id
    result["send_ok"] = send.ok
    result["send_detail"] = send.detail
    if _channel_key(task) == "跟进":
        db.add(
            Alert(
                tenant_id=task.tenant_id,
                task_id=task.id,
                alert_type="跟进提醒",
                message=f"{task.title} 已自动触达，请关注客户回访结果",
            )
        )
    db.add(
        FeedbackEvent(
            tenant_id=task.tenant_id,
            task_id=task.id,
            action=f"自动执行-{task.channel}",
            note=result["content"],
            occurred_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
    )
    task.result_json = result
    task.status = "已完成"
    db.commit()
    _refresh_acceptance(db, task.instruction_id)
    return {"status": task.status, "message_id": send.message_id}


def _refresh_acceptance(db: Session, instruction_id: str | None) -> None:
    if not instruction_id:
        return
    instruction = db.get(Instruction, instruction_id)
    if instruction is None:
        return
    children = _children_of(db, instruction)
    if not children:
        return
    terminal = {"已完成", "已拦截", "已失败"}
    if any(task.status not in terminal for task in children):
        return
    summary = build_acceptance_summary(db, instruction)
    strategy_ids = dict(instruction.strategy_ids_json or {})
    strategy_ids["acceptance_report"] = summary
    instruction.strategy_ids_json = strategy_ids
    parent = (
        db.get(StrategyTask, strategy_ids.get("parent_task_id"))
        if strategy_ids.get("parent_task_id")
        else None
    )
    if parent:
        parent.status = "已完成"
        result = dict(parent.result_json or {})
        result["acceptance_report"] = summary
        parent.result_json = result
    db.commit()


def build_acceptance_summary(db: Session, instruction: Instruction) -> dict:
    children = _children_of(db, instruction)
    status_counts: dict[str, int] = {}
    channel_status: list[dict] = []
    for task in children:
        status_counts[task.status] = status_counts.get(task.status, 0) + 1
        channel_status.append(
            {
                "title": task.title,
                "channel": task.channel,
                "status": task.status,
                "due_at": task.due_at,
                "message_id": (task.result_json or {}).get("message_id"),
                "content": _short((task.result_json or {}).get("content") or task.script or "", 200),
            }
        )
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(children),
        "status_counts": status_counts,
        "channels": channel_status,
    }


def _split_metrics(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in re.split(r"[、,，;；/|]", value) if item.strip()]


def _parse_number(text: str | int | float | None) -> float | None:
    if text is None:
        return None
    value = str(text).strip().replace(",", "").replace("，", "").replace("%", "")
    if not value:
        return None
    multiplier = 1.0
    if value.endswith("万"):
        multiplier = 10000.0
        value = value[:-1]
    try:
        return float(value) * multiplier
    except ValueError:
        return None


def _kpi_comparison_lines(instruction: Instruction, kpi_results: dict | None) -> list[str]:
    params = instruction.params_json or {}
    asset = instruction.asset_json or {}
    metrics = _split_metrics(params.get("kpi_metrics")) or (asset.get("kpi_targets") or [])
    goal_value = params.get("goal_value") or (asset.get("activity_plan") or {}).get("goal") or ""
    results = kpi_results or {}
    lines = ["KPI 对比："]
    if not metrics:
        lines.append("- 未设置 KPI 指标")
        return lines
    for metric in metrics:
        target_text = goal_value if metric in {"GMV", "销售额", "业绩", "营收", "储值额"} else ""
        actual = results.get(metric)
        if actual is None:
            lines.append(f"- {metric}：目标 {target_text or '待确认'} / 实际 待回填")
            continue
        line = f"- {metric}：目标 {target_text or '待确认'} / 实际 {actual}"
        target_num = _parse_number(target_text)
        actual_num = _parse_number(actual)
        if target_num and actual_num is not None:
            rate = actual_num / target_num * 100
            line += f" / 达成率 {rate:.1f}%"
        lines.append(line)
    return lines


def build_acceptance_report_text(
    instruction: Instruction,
    summary: dict,
    kpi_results: dict | None = None,
) -> str:
    lines = [
        f"执行验收报告：{instruction.title}",
        f"生成时间：{summary.get('generated_at', '')}",
        f"渠道任务：{summary.get('total', 0)} 个",
        "状态："
        + "，".join(f"{status} {count} 个" for status, count in summary.get("status_counts", {}).items()),
        "",
        "执行明细：",
    ]
    for item in summary.get("channels", []):
        lines.append(
            f"- {item['title']}（{item['status']}，截止 {item['due_at'] or '-'}）\n  {item['content']}"
        )
    lines.append("")
    lines.extend(_kpi_comparison_lines(instruction, kpi_results))
    return "\n".join(lines)
